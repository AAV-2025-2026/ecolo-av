//! `--esp32 ws://...`: the ESP32's JSON status lines, read on a thread of their own
//! (`esp32`), as a second source beside ROS or the demo (review 2, M9). Read only: the
//! only bytes it sends are the WebSocket's opening, and a pong or a close the protocol
//! asks for. Its news goes only to the GRAPHS page's data and its status strip, never
//! to the buttons, the gate or the calibration page's rules.
//!
//! It tries again every 2 s while the board can't be reached, and drops lines when the
//! window falls behind (the line numbers then show the gap).

use std::{
    io::{ErrorKind, Read, Write},
    net::{TcpStream, ToSocketAddrs},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver, SyncSender},
        Arc,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use anyhow::{bail, Context as _, Result};
use panel_core::{
    esp32::parse_line,
    state::{Esp32News, Update},
    ws::{self, Decoder, Message, Opcode, Url},
};

/// How many pieces of news may wait for the window.
const QUEUE: usize = 1024;
/// Between tries to reach the board.
const RETRY: Duration = Duration::from_secs(2);
/// The board sends a heartbeat each second: this long without a byte is a lost link.
const SILENCE: Duration = Duration::from_secs(5);
const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
/// How often a blocked read wakes, to see whether to stop.
const POLL: Duration = Duration::from_millis(200);
/// The opening answer's head, at most.
const HEAD_MAX: usize = 8 * 1024;

/// The reader, seen from the window.
pub struct Esp32Reader {
    news: Receiver<Esp32News>,
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

impl Esp32Reader {
    pub fn start(url: Url) -> Result<Self> {
        let (tx, news) = mpsc::sync_channel(QUEUE);
        let stop = Arc::new(AtomicBool::new(false));
        let thread = {
            let stop = Arc::clone(&stop);
            thread::Builder::new()
                .name("esp32".into())
                .spawn(move || run(&url, &tx, &stop))?
        };
        Ok(Self {
            news,
            stop,
            thread: Some(thread),
        })
    }

    /// Everything that came since the last call. Never blocks.
    pub fn drain(&mut self) -> impl Iterator<Item = Update> + '_ {
        self.news.try_iter().map(Update::Esp32)
    }
}

impl Drop for Esp32Reader {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(t) = self.thread.take() {
            let _ = t.join();
        }
    }
}

fn send(tx: &SyncSender<Esp32News>, news: Esp32News) {
    // Full: the window is far behind; the line numbers show what was lost.
    let _ = tx.try_send(news);
}

/// The thread: connect, read until it ends, wait, again; until told to stop.
fn run(url: &Url, tx: &SyncSender<Esp32News>, stop: &AtomicBool) {
    while !stop.load(Ordering::SeqCst) {
        send(tx, Esp32News::Connecting(url.to_string()));
        let why = match session(url, tx, stop) {
            Ok(()) => "the board closed the connection".to_owned(),
            Err(e) => format!("{e:#}"),
        };
        if stop.load(Ordering::SeqCst) {
            break;
        }
        send(tx, Esp32News::Lost(why));
        let until = Instant::now() + RETRY;
        while Instant::now() < until && !stop.load(Ordering::SeqCst) {
            thread::sleep(POLL);
        }
    }
}

/// 16 bytes for the opening's key, and 4 for the masks: different each run.
fn nonce() -> [u8; 16] {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos());
    let mixed = nanos ^ (u128::from(std::process::id()) << 64);
    mixed.to_le_bytes()
}

/// One connection, until it ends.
fn session(url: &Url, tx: &SyncSender<Esp32News>, stop: &AtomicBool) -> Result<()> {
    let addr = (url.host.as_str(), url.port)
        .to_socket_addrs()
        .with_context(|| format!("finding {}", url.host))?
        .next()
        .with_context(|| format!("no address for {}", url.host))?;
    let mut stream = TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT)
        .with_context(|| format!("reaching {url}"))?;
    stream.set_read_timeout(Some(POLL))?;
    stream.set_nodelay(true)?;
    let key = nonce();
    stream.write_all(ws::request(url, key).as_bytes())?;

    // The answer's head, then whatever came after it is the first frames.
    let mut buf = Vec::new();
    let started = Instant::now();
    let head_end = loop {
        if let Some(i) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
            break i + 4;
        }
        if buf.len() > HEAD_MAX {
            bail!("the board's answer is too long for a WebSocket's");
        }
        if started.elapsed() > SILENCE {
            bail!("no answer from {url}");
        }
        read_some(&mut stream, &mut buf)?;
    };
    ws::check_answer(&String::from_utf8_lossy(&buf[..head_end]))?;
    send(tx, Esp32News::Connected);

    let mut decoder = Decoder::default();
    decoder.push(&buf[head_end..]);
    let mask = [key[0], key[5], key[10], key[15]];
    let mut heard = Instant::now();
    loop {
        while let Some(message) = decoder.message() {
            match message? {
                Message::Text(text) => {
                    for line in text.lines().filter(|l| !l.trim().is_empty()) {
                        send(
                            tx,
                            match parse_line(line) {
                                Ok(l) => Esp32News::Line(l),
                                Err(e) => Esp32News::Unreadable(e.to_string()),
                            },
                        );
                    }
                }
                Message::Ping(payload) => {
                    stream.write_all(&ws::client_frame(Opcode::Pong, &payload, mask))?;
                }
                Message::Close => {
                    let _ = stream.write_all(&ws::client_frame(Opcode::Close, &[], mask));
                    return Ok(());
                }
                Message::Binary(_) | Message::Pong => {}
            }
        }
        if stop.load(Ordering::SeqCst) {
            let _ = stream.write_all(&ws::client_frame(Opcode::Close, &[], mask));
            return Ok(());
        }
        let mut chunk = Vec::new();
        if read_some(&mut stream, &mut chunk)? > 0 {
            heard = Instant::now();
            decoder.push(&chunk);
        } else if heard.elapsed() > SILENCE {
            bail!("silent for {} s", SILENCE.as_secs());
        }
    }
}

/// Reads what's there into `buf`: the count, 0 after a quiet `POLL`. The end of the
/// stream is an error.
fn read_some(stream: &mut TcpStream, buf: &mut Vec<u8>) -> Result<usize> {
    let mut chunk = [0u8; 4096];
    match stream.read(&mut chunk) {
        Ok(0) => bail!("the connection ended"),
        Ok(n) => {
            buf.extend_from_slice(&chunk[..n]);
            Ok(n)
        }
        Err(e) if matches!(e.kind(), ErrorKind::WouldBlock | ErrorKind::TimedOut) => Ok(0),
        Err(e) => Err(e.into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    /// A pretend board on this computer (127.0.0.1, a port of its own): it answers the
    /// opening, sends the contract's golden lines in one text frame, pings, and closes.
    #[test]
    fn reads_the_golden_lines_from_a_pretend_board() -> Result<()> {
        let listener = TcpListener::bind("127.0.0.1:0")?;
        let port = listener.local_addr()?.port();
        let board = thread::spawn(move || -> Result<Vec<u8>> {
            let (mut s, _) = listener.accept()?;
            s.set_read_timeout(Some(Duration::from_secs(5)))?;
            let mut head = Vec::new();
            while !head.windows(4).any(|w| w == b"\r\n\r\n") {
                let mut b = [0u8; 512];
                let n = s.read(&mut b)?;
                head.extend_from_slice(&b[..n]);
            }
            s.write_all(
                b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\
                  Connection: Upgrade\r\n\r\n",
            )?;
            let golden = include_str!("../../../../../../firmware/status/golden.jsonl");
            let mut frame = vec![0x81, 126];
            frame.extend_from_slice(&(golden.len() as u16).to_be_bytes());
            frame.extend_from_slice(golden.as_bytes());
            frame.extend_from_slice(&[0x89, 0x02, b'h', b'i']);
            frame.extend_from_slice(&[0x88, 0x00]);
            s.write_all(&frame)?;
            // What the panel sent after the opening: its pong and its close.
            let mut back = Vec::new();
            let deadline = Instant::now() + Duration::from_secs(5);
            while back.len() < 14 && Instant::now() < deadline {
                let mut b = [0u8; 64];
                match s.read(&mut b) {
                    Ok(0) => break,
                    Ok(n) => back.extend_from_slice(&b[..n]),
                    Err(_) => break,
                }
            }
            Ok(back)
        });
        let url = Url::parse(&format!("ws://127.0.0.1:{port}/"))?;
        let (tx, rx) = mpsc::sync_channel(QUEUE);
        let stop = AtomicBool::new(false);
        session(&url, &tx, &stop)?;
        let news: Vec<Esp32News> = rx.try_iter().collect();
        assert_eq!(news.first(), Some(&Esp32News::Connected));
        let lines = news
            .iter()
            .filter(|n| matches!(n, Esp32News::Line(_)))
            .count();
        assert_eq!(lines, 7, "{news:?}");
        let back = board
            .join()
            .map_err(|_| anyhow::anyhow!("the board panicked"))??;
        // A masked pong with "hi", then a masked close: nothing else.
        let mut d = Decoder::default();
        d.push(&back);
        assert_eq!(d.message(), Some(Ok(Message::Pong)));
        assert_eq!(d.message(), Some(Ok(Message::Close)));
        assert_eq!(d.message(), None);
        Ok(())
    }

    #[test]
    fn nobody_there_is_an_error_not_a_hang() {
        // Port 9 (discard) on this computer: nothing listens there on a laptop.
        let url = Url::parse("ws://127.0.0.1:9/").expect("valid");
        let (tx, _rx) = mpsc::sync_channel(QUEUE);
        let started = Instant::now();
        assert!(session(&url, &tx, &AtomicBool::new(false)).is_err());
        assert!(started.elapsed() < Duration::from_secs(10));
    }
}
