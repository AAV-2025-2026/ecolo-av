import { Pressable, FlatList, Text, StyleSheet, View } from 'react-native';

export default function SearchResults() {
  const groupedData = [
    {
      label: '1 day ago',
      items: [
        { title: 'Recent Search 1', subtitle: 'Subtitle A' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
      ],
    },
    {
      label: '2 weeks ago',
      items: [
        { title: 'Old Search 1', subtitle: 'Subtitle C' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
        { title: 'Recent Search 2', subtitle: 'Subtitle B' },
      ],
    },
    {
      label: '1 month ago',
      items: [
        { title: 'Archived Search 1', subtitle: 'Subtitle E' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
        { title: 'Old Search 2', subtitle: 'Subtitle D' },
      ],
    },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <CustomButton title="🏠 Home" variant="half" onPress={() => {}} />
        <Divider vertical />
        <CustomButton title="💼 Work" variant="half" onPress={() => {}} />
      </View>

      <FlatList
        data={groupedData}
        keyExtractor={(group) => group.label}
        renderItem={({ item: group, index }) => (
          <View>
            <Text style={styles.groupLabel}>{group.label}</Text>

            {group.items.map((search, i) => (
              <CustomButton
                key={search.title}
                title={search.title}
                subtitle={search.subtitle}
                variant="full"
                onPress={() => {}}
              />
            ))}

            {index < groupedData.length - 1 && <Divider />}
          </View>
        )}
        showsVerticalScrollIndicator={false}
      />
    </View>
  );
}

function CustomButton({ title, subtitle, onPress, variant = 'full' }) {
  const isFull = variant === 'full';

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        isFull ? styles.full : styles.half,
        pressed && styles.pressed,
      ]}
    >
      {isFull ? (
        <View style={styles.textContainer}>
          <Text style={styles.title}>{title}</Text>
          {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
        </View>
      ) : (
        <Text style={styles.centerText}>{title}</Text>
      )}
    </Pressable>
  );
}

function Divider({ vertical = false }) {
  return (
    <View
      style={[
        styles.divider,
        vertical ? styles.dividerVertical : styles.dividerHorizontal,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 10,
    width: '100%',
  },

  row: {
    flexDirection: 'row',
    marginBottom: 10,
    alignItems: 'center',
  },

  button: {
    backgroundColor: '#fff',
    paddingVertical: 12,
    borderRadius: 10,
    marginBottom: 0,
    paddingHorizontal: 16,
    justifyContent: 'center',
  },

  full: {
    alignItems: 'flex-start',
    alignSelf: 'stretch',
  },

  half: {
    flex: 1,
    alignItems: 'center',
  },

  pressed: {
    backgroundColor: '#f2f2f2',
  },

  textContainer: {
    width: '100%',
  },

  title: {
    color: '#000',
    fontSize: 18,
    fontWeight: '700',
  },

  subtitle: {
    color: '#444',
    fontSize: 14,
    marginTop: 2,
  },

  centerText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },

  divider: {
    backgroundColor: '#e5e5e5',
  },
  dividerHorizontal: {
    height: 1,
    width: '100%',
    alignSelf: 'stretch',
    marginVertical: 10,
  },
  dividerVertical: {
    width: 1,
    height: '100%',
    marginHorizontal: 6,
  },

  groupLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#666',
    marginBottom: 6,
    marginTop: 10,
    paddingHorizontal: 4,
  },
});
