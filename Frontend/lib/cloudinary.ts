/**
 * lib/cloudinary.ts — direct-to-Cloudinary image upload (unsigned preset).
 *
 * The app never proxies image bytes through the backend: the picked image is
 * POSTed straight to Cloudinary's upload API with an unsigned preset, and only
 * the resulting https delivery URL is stored on the user's account.
 *
 * Configure in Frontend/.env:
 *   EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME    — dashboard home page
 *   EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET — an *unsigned* upload preset
 */
const CLOUD_NAME = process.env.EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME ?? '';
const UPLOAD_PRESET = process.env.EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET ?? '';

export const cloudinaryConfigured = (): boolean => Boolean(CLOUD_NAME && UPLOAD_PRESET);

/**
 * Upload a picked image and return its secure delivery URL.
 * `dataUri` is a base64 data URI (expo-image-picker gives one with base64:true).
 */
export async function uploadAvatar(dataUri: string): Promise<string> {
  if (!cloudinaryConfigured()) {
    throw new Error(
      'Cloudinary is not configured. Fill EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME and ' +
        'EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET in Frontend/.env, then restart Expo.',
    );
  }

  const form = new FormData();
  form.append('file', dataUri);
  form.append('upload_preset', UPLOAD_PRESET);
  form.append('folder', 'tripsmart/avatars');

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
