// App.js
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import SearchBar from './components/SearchBar';
import SearchResults from './components/SearchResults';
import TopStatusBar from './components/TopStatusBar';
import Speed from './components/Speed'

export default function App() {
  return (
    <View style={styles.container}>
      <TopStatusBar />

      <View style={styles.content}>
        {/* Sidebar */}
        <View style={styles.sidecontainer}>
          <SearchBar style={{ marginBottom: 10 }} />
          <SearchResults />
        </View>
        <Speed/>
      </View>

      <StatusBar style="auto" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#25292e',
  },
  content: {
    flex: 1,
    flexDirection: 'row', 
  },
  sidecontainer: {
    width: '28%', 
    padding: 10,
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: 10,
  },
});
