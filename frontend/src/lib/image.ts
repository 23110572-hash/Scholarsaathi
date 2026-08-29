/**
 * Profile photos are stored in the database as a base64 data URL, so the browser
 * downscales and re-encodes the picked file before upload. A 320px square JPEG keeps a
 * typical phone photo well under the backend's 300 KB data-URL ceiling.
 */
const MAX_EDGE_PX = 320
const JPEG_QUALITY = 0.82
const MAX_SOURCE_BYTES = 12 * 1024 * 1024
export const MAX_PHOTO_DATA_URL_LENGTH = 300_000

export const ACCEPTED_PHOTO_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const

export class ImageProcessingError extends Error {}

function loadImage(dataUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new ImageProcessingError('That image could not be read.'))
    image.src = dataUrl
  })
}

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(new ImageProcessingError('That file could not be read.'))
    reader.readAsDataURL(file)
  })
}

/**
 * Centre-crops to a square, scales down to at most MAX_EDGE_PX, and returns a JPEG data
 * URL. Throws ImageProcessingError with a message safe to show the user.
 */
export async function toSquareAvatarDataUrl(file: File): Promise<string> {
  if (!ACCEPTED_PHOTO_TYPES.includes(file.type as (typeof ACCEPTED_PHOTO_TYPES)[number])) {
    throw new ImageProcessingError('Choose a PNG, JPEG, or WebP image.')
  }
  if (file.size > MAX_SOURCE_BYTES) {
    throw new ImageProcessingError('Choose an image smaller than 12 MB.')
  }

  const image = await loadImage(await readAsDataUrl(file))
  const edge = Math.min(image.naturalWidth, image.naturalHeight)
  if (!edge) throw new ImageProcessingError('That image appears to be empty.')

  const target = Math.min(edge, MAX_EDGE_PX)
  const canvas = document.createElement('canvas')
  canvas.width = target
  canvas.height = target
  const context = canvas.getContext('2d')
  if (!context) throw new ImageProcessingError('Your browser could not process that image.')

  context.drawImage(
    image,
    (image.naturalWidth - edge) / 2,
    (image.naturalHeight - edge) / 2,
    edge,
    edge,
    0,
    0,
    target,
    target,
  )

  const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
  if (dataUrl.length > MAX_PHOTO_DATA_URL_LENGTH) {
    throw new ImageProcessingError('That image is too detailed to store. Try a simpler photo.')
  }
  return dataUrl
}
