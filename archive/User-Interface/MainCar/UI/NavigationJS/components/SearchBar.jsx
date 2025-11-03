import { View, TextInput, StyleSheet } from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';

export default function SearchBar() {
  return (
    <View
      style={[
        styles.searchBarContainer
      ]}
    >
      <FontAwesome5 name="search" size={24} color="#000" />
      <TextInput
        style={styles.input}
        placeholder="Search..."
        placeholderTextColor="#888"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  searchBarContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#ccc',
    paddingHorizontal: 12,
    width: '100%',
    height: '6%',
  },
  input: {
    flex: 1,      
    marginLeft: 8,
    fontSize: 20,
    padding: 0,      
  },
});
