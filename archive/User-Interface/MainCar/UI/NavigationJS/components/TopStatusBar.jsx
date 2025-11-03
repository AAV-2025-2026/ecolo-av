import { View, Text, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function TopStatusBar() {
  return (
    <View style={styles.container }>
      <LinearGradient
        colors={['rgba(255, 255, 255, 1)', 'rgba(0,0,0,0)']}  
        style={StyleSheet.absoluteFill}
      />
      <Text style={{ flex: 1 }}>Time + Temp</Text>
      <Text style={{ flex: 1, textAlign: 'center' }}>Compass</Text>
      <Text style={{ flex: 1, textAlign: 'right' }}>Battery</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',           
    justifyContent: 'space-between', 
    width: '100%',
    height: 40,                     
    paddingHorizontal: 12,
  },
});
