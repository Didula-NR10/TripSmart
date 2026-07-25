/**
 * lib/cloudinary.ts — direct-to-Cloudinary image upload (unsigned preset).
 *
 * The app never proxies image bytes through the backend: the picked image is
 * POSTed straight to Cloudinary's upload API with an unsigned preset, and only
 * the resulting https delivery URL is stored on the user's account (or, for
 * journal pages, on the note row).
 */
const CLOUD_NAME = 'qftg18mi';
const UPLOAD_PRESET = 'pxkwgkig';

/**
 * Upload a picked image to a given Cloudinary folder and return its secure
 * delivery URL. `dataUri` is a base64 data URI (expo-image-picker gives one
 * with base64:true).
 */
async function uploadImage(dataUri: string, folder: string): Promise<string> {
  const form = new FormData();
  form.append('file', dataUri);
  form.append('upload_preset', UPLOAD_PRESET);
  form.append('folder', folder);

  const res = await fetch(`https://api.cloudinary.com/v1_1/${CLOUD_NAME}/image/upload`, {
    method: 'POST',
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.secure_url) {
    throw new Error(data?.error?.message ?? `Cloudinary upload failed (${res.status}).`);
  }
  return data.secure_url as string;
}

export const uploadAvatar = (dataUri: string) => uploadImage(dataUri, 'tripsmart/avatars');

export const uploadJournalPhoto = (dataUri: string) => uploadImage(dataUri, 'tripsmart/journal');
