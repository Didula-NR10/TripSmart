import { useState } from 'react';
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { districts } from '../../constants/districts';
import { Palette, Radius, Space, Type } from '../../constants/trip-theme';

type Props = {
  visible: boolean;
  onClose: () => void;
  onSelect: (key: string) => void;
  title?: string;
  /** Show an "All Sri Lanka" row on top that selects the pseudo-key 'all'. */
  allOption?: boolean;
};

export function DistrictSheet({
  visible,
  onClose,
  onSelect,
  title = 'Select a district',
  allOption = false,
}: Props) {
  const [query, setQuery] = useState('');
  const list = districts.filter((d) =>
    d.name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.scrim}>
        <View style={styles.sheet}>
          <View style={styles.grabber} />
          <View style={styles.head}>
            <Text style={styles.title}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={10}>
              <Ionicons name="close" size={20} color={Palette.textMuted} />
            </Pressable>
          </View>

          <View style={styles.search}>
            <Ionicons name="search" size={15} color={Palette.textDim} />
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Search 25 districts"
              placeholderTextColor={Palette.textDim}
              style={styles.input}
            />
          </View>

          {allOption && query.trim() === '' ? (
            <Pressable
              style={styles.row}
              onPress={() => {
                onSelect('all');
                setQuery('');
                onClose();
              }}
            >
              <View>
                <Text style={styles.name}>All Sri Lanka</Text>
                <Text style={styles.meta}>Show every district, island-wide</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={Palette.textDim} />
            </Pressable>
          ) : null}

          <FlatList
            data={list}
            keyExtractor={(d) => d.key}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => (
              <Pressable
                style={styles.row}
                onPress={() => {
                  onSelect(item.key);
                  setQuery('');
                  onClose();
                }}
              >
                <View>
                  <Text style={styles.name}>{item.name}</Text>
                  <Text style={styles.meta}>
                    {item.province} · {item.zone} zone · {item.elevation} m
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color={Palette.textDim} />
              </Pressable>
            )}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: 'rgba(9, 34, 38, 0.45)',
    justifyContent: 'flex-end',
  },
  sheet: {
    height: '78%',
    backgroundColor: Palette.surface,
    borderTopLeftRadius: Radius.xxl,
    borderTopRightRadius: Radius.xxl,
    paddingHorizontal: Space.xl,
    paddingBottom: Space.xl,
  },
  grabber: {
    alignSelf: 'center',
    width: 38,
    height: 4,
    borderRadius: Radius.pill,
    backgroundColor: Palette.border,
    marginTop: Space.md,
  },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: Space.lg,
  },
  title: {
    ...Type.title,
    color: Palette.text,
  },
  search: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Space.sm,
    backgroundColor: Palette.canvas,
    borderRadius: Radius.md,
    paddingHorizontal: Space.md,
    marginTop: Space.lg,
    marginBottom: Space.sm,
  },
  input: {
    flex: 1,
    height: 42,
    ...Type.body,
    color: Palette.text,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: Space.md,
    borderBottomWidth: 1,
    borderBottomColor: Palette.borderSoft,
  },
  name: {
    ...Type.label,
    color: Palette.text,
  },
  meta: {
    ...Type.caption,
    color: Palette.textMuted,
    marginTop: 2,
    textTransform: 'capitalize',
  },
});
