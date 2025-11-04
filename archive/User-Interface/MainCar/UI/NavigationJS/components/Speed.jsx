import { Text, StyleSheet, View } from 'react-native';
import { useEffect, useState } from 'react';
import io from "socket.io-client";

export default function Speed() {
  const [speed, setSpeed] = useState("Waiting...");

    useEffect(() => {
      // Change IP to your Flask server’s local IP
      const socket = io("http://ServerIP:Port"); 

      socket.on("connect", () => {
        console.log("Connected to Flask server");
      });

      socket.on("speed_update", (data) => {
        setTime(data.speed);
      });

      socket.on("disconnect", () => {
        console.log("Disconnected");
      });

      return () => socket.disconnect();
    }, []);

  return (
    <View style={styles.container}>
      <Text style={styles.text}>{time}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    borderRadius: 16,
    padding: 10,
    width: 50,
  },
   text: {
    color: '#FFF',
    fontSize: 48,
  },
});
