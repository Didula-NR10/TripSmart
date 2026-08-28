import { useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { uploadJournalPhoto } from '../../lib/cloudinary';
import { JournalFont, JournalPalette } from './JournalTheme';

export function WriteForm({
  onCancel,
  onSave,
}: {
  onCancel: () => void;
  onSave: (entry: { place: string; body: string; photoUrl: string }) => Promise<void>;
}) {
  const [place, setPlace] = useState('');
  const [body, setBody] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [photoBusy, setPhotoBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickPhoto = async () => {
    setError(null);
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setError('Photo permission denied.');
      return;
    }
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
      base64: true,
    });
    if (picked.canceled || !picked.assets?.[0]?.base64) return;
    const asset = picked.assets[0];
    setPhotoBusy(true);
    try {
      const url = await uploadJournalPhoto(
        `data:${asset.mimeType ?? 'image/jpeg'};base64,${asset.base64}`,
      );
      setPhotoUrl(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Photo upload failed.');
    } finally {
      setPhotoBusy(false);
    }
  };

  const save = async () => {
    if (!place.trim() || !body.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onSave({ place: place.trim(), body: body.trim(), photoUrl });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the page.');
      setSaving(false);
    }
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>Where did you go?</Text>
      <TextInput
        value={place}
        onChangeText={setPlace}
        placeholder="e.g. Sigiriya, Ella Rock"
        placeholderTextColor={JournalPalette.inkFaded}
        style={styles.input}
      />

      <Text style={styles.label}>What did you see?</Text>
      <TextInput
        value={body}
        onChangeText={setBody}
        placeholder="The view, the food, the people…"
        placeholderTextColor={JournalPalette.inkFaded}
        multiline
        style={[styles.input, styles.multiline]}
      />

      <Pressable style={styles.photoPicker} onPress={pickPhoto} disabled={photoBusy}>
        {photoBusy ? (
          <ActivityIndicator color={JournalPalette.wax} />
        ) : photoUrl ? (
          <>
            <Image source={{ uri: photoUrl }} style={styles.photoPreview} />
            <Text style={styles.photoPickerText}>Tap to change photo</Text>
          </>
        ) : (
          <>
            <Ionicons name="camera-outline" size={20} color={JournalPalette.wax} />
            <Text style={styles.photoPickerText}>Glue in a photo (optional)</Text>
          </>
        )}
      </Pressable>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <View style={styles.actions}>
        <Pressable style={styles.cancel} onPress={onCancel} disabled={saving}>
          <Text style={styles.cancelText}>Cancel</Text>
        </Pressable>
        <Pressable
          style={[styles.save, (saving || !place.trim() || !body.trim()) && styles.saveOff]}
          onPress={save}
          disabled={saving || !place.trim() || !body.trim()}
        >
          {saving ? (
            <ActivityIndicator size="small" color={JournalPalette.parchment} />
          ) : (
            <Text style={styles.saveText}>Save page</Text>
          )}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    backgroundColor: JournalPalette.parchment,
    borderRadius: 6,
    padding: 20,
  },
  label: {
    fontFamily: JournalFont.serifBold,
    fontSize: 13,
    color: JournalPalette.ink,
    marginBottom: 6,
    marginTop: 12,
  },
  input: {
    backgroundColor: JournalPalette.parchmentDeep,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: JournalPalette.parchmentEdge,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontFamily: JournalFont.hand,
    fontSize: 19,
    color: JournalPalette.ink,
  },
  multiline: {
    height: 96,
    textAlignVertical: 'top',
  },
  photoPicker: {
    marginTop: 14,
    borderRadius: 8,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: JournalPalette.gold,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  photoPreview: {
    width: 64,
    height: 64,
    borderRadius: 4,
  },
  photoPickerText: {
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.inkFaded,
  },
  error: {
    fontFamily: JournalFont.serif,
    fontSize: 12,
    color: JournalPalette.danger,
    marginTop: 10,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 16,
  },
  cancel: {
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  cancelText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 13,
    color: JournalPalette.inkFaded,
  },
  save: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: JournalPalette.wax,
    minWidth: 100,
    alignItems: 'center',
  },
  saveOff: { opacity: 0.5 },
  saveText: {
    fontFamily: JournalFont.serifBold,
    fontSize: 13,
    color: JournalPalette.parchment,
  },
});
