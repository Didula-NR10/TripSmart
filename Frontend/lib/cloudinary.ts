const CLOUD_NAME = 'qftg18mi';
const UPLOAD_PRESET = 'pxkwgkig';

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
