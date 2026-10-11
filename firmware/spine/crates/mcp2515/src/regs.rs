//! The MCP2515's SPI instructions and registers, from Microchip's *MCP2515 Stand-Alone CAN
//! Controller with SPI Interface* data sheet (DS20001801K): Table 12-1 (instructions) and
//! Table 11-1 (register map). Private: the rest of the crate turns them into types.

/// The receive buffers, RXB0 and RXB1.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RxBuffer {
    Rxb0,
    Rxb1,
}

impl RxBuffer {
    /// RXB0 first: with rollover on, it holds the older frame.
    pub const ALL: [RxBuffer; 2] = [RxBuffer::Rxb0, RxBuffer::Rxb1];

    const fn index(self) -> u8 {
        match self {
            RxBuffer::Rxb0 => 0,
            RxBuffer::Rxb1 => 1,
        }
    }
}

/// The transmit buffers, TXB0 to TXB2.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TxBuffer {
    Txb0,
    Txb1,
    Txb2,
}

impl TxBuffer {
    pub const ALL: [TxBuffer; 3] = [TxBuffer::Txb0, TxBuffer::Txb1, TxBuffer::Txb2];

    const fn index(self) -> u8 {
        match self {
            TxBuffer::Txb0 => 0,
            TxBuffer::Txb1 => 1,
            TxBuffer::Txb2 => 2,
        }
    }
}

/// The SPI instructions this driver uses (Table 12-1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Instruction {
    Reset,
    Read,
    Write,
    BitModify,
    ReadStatus,
    /// READ RX BUFFER, from the buffer's SIDH. Raising CS clears its RXnIF flag.
    ReadRxBuffer(RxBuffer),
    /// LOAD TX BUFFER, from the buffer's SIDH.
    LoadTxBuffer(TxBuffer),
    /// RTS: start sending one buffer.
    RequestToSend(TxBuffer),
}

impl Instruction {
    pub const fn byte(self) -> u8 {
        match self {
            Instruction::Reset => 0xC0,
            Instruction::Read => 0x03,
            Instruction::Write => 0x02,
            Instruction::BitModify => 0x05,
            Instruction::ReadStatus => 0xA0,
            // 1001 0nm0: n = 1 for RXB1, m = 0 to start at SIDH.
            Instruction::ReadRxBuffer(b) => 0x90 | (b.index() << 2),
            // 0100 0abc: ab = the buffer, c = 0 to start at SIDH.
            Instruction::LoadTxBuffer(b) => 0x40 | (b.index() << 1),
            // 1000 0nnn: one bit a buffer.
            Instruction::RequestToSend(b) => 0x80 | (1 << b.index()),
        }
    }
}

/// The registers this driver reads or writes, by address (Table 11-1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Register {
    /// Filters 0 to 2 (RXF0SIDH, 4 bytes each).
    Rxf0 = 0x00,
    /// CANSTAT, then CANCTRL. Both also appear at the end of every 16-byte row of the map
    /// (0x1E, 0x1F, 0x2E, ...), so one read can take them with the registers before them.
    CanStat = 0x0E,
    CanCtrl = 0x0F,
    /// Filters 3 to 5 (RXF3SIDH, 4 bytes each).
    Rxf3 = 0x10,
    /// TEC, then REC, then CANSTAT's copy at 0x1E.
    Tec = 0x1C,
    /// Masks 0 and 1 (RXM0SIDH, 4 bytes each).
    Rxm0 = 0x20,
    /// CNF3, CNF2, CNF1 and CANINTE, in that order.
    Cnf3 = 0x28,
    Eflg = 0x2D,
    Rxb0Ctrl = 0x60,
    Rxb1Ctrl = 0x70,
}

impl Register {
    pub const fn address(self) -> u8 {
        self as u8
    }
}

/// CANCTRL just after a reset: configuration mode, CLKOUT on at Fosc/8 (Register 10-1).
pub const CANCTRL_AFTER_RESET: u8 = 0x87;

/// CANCTRL's REQOP and CANSTAT's OPMOD, bits 7 to 5 (Registers 10-1 and 10-2): 000 normal,
/// 001 sleep, 010 loopback, 011 listen-only, 100 configuration.
pub const MODE_SHIFT: u8 = 5;
pub const MODE_CONFIGURATION: u8 = 0b100;

/// CANINTE: interrupt on a received frame only (RX0IE, RX1IE), so the INT pin means "a frame
/// is waiting" (Register 7-1).
pub const RX_INTERRUPTS: u8 = 0b0000_0011;

/// RXBnCTRL: RXM = 11, the filters off: every frame (Register 4-1).
pub const RXM_ANY: u8 = 0b0110_0000;
/// RXB0CTRL: BUKT, roll a frame over into RXB1 when RXB0 is full (Register 4-1).
pub const BUKT: u8 = 0b0000_0100;

/// EFLG bits (Register 6-3).
pub mod eflg {
    pub const RX1OVR: u8 = 0x80;
    pub const RX0OVR: u8 = 0x40;
    pub const TXBO: u8 = 0x20;
    pub const TXEP: u8 = 0x10;
    pub const RXEP: u8 = 0x08;
    pub const EWARN: u8 = 0x01;
    /// A frame was lost: it arrived with its buffers full.
    pub const OVERFLOW: u8 = RX0OVR | RX1OVR;
}

/// READ STATUS bits (Figure 12-8): RX0IF, RX1IF, then each TX buffer's TXREQ and TXnIF.
pub const fn status_rx_full(b: RxBuffer) -> u8 {
    1 << b.index()
}

pub const fn status_tx_pending(b: TxBuffer) -> u8 {
    1 << (2 + 2 * b.index())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn instruction_bytes_are_table_12_1() {
        use Instruction::*;
        assert_eq!(Reset.byte(), 0b1100_0000);
        assert_eq!(Read.byte(), 0b0000_0011);
        assert_eq!(Write.byte(), 0b0000_0010);
        assert_eq!(BitModify.byte(), 0b0000_0101);
        assert_eq!(ReadStatus.byte(), 0b1010_0000);
        assert_eq!(ReadRxBuffer(RxBuffer::Rxb0).byte(), 0x90);
        assert_eq!(ReadRxBuffer(RxBuffer::Rxb1).byte(), 0x94);
        let loads = TxBuffer::ALL.map(|b| LoadTxBuffer(b).byte());
        assert_eq!(loads, [0x40, 0x42, 0x44]);
        let sends = TxBuffer::ALL.map(|b| RequestToSend(b).byte());
        assert_eq!(sends, [0x81, 0x82, 0x84]);
    }

    #[test]
    fn status_bits_are_figure_12_8() {
        assert_eq!(status_rx_full(RxBuffer::Rxb0), 0x01);
        assert_eq!(status_rx_full(RxBuffer::Rxb1), 0x02);
        let pending = TxBuffer::ALL.map(status_tx_pending);
        assert_eq!(pending, [0x04, 0x10, 0x40]);
    }
}
