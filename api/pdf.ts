import { AwsClient } from 'aws4fetch'

declare const process: { env: Record<string, string | undefined> }

export const config = { runtime: 'edge' }

const BUCKET = process.env.R2_BUCKET || 'school-tender-pdfs'

export default async function handler(req: Request): Promise<Response> {
  const key = new URL(req.url).searchParams.get('key') || ''
  if (!/^pdf\/\d{4}-\d{2}\/[\w-]+\.\w{1,5}$/.test(key)) return new Response('Bad key', { status: 400 })
  const endpoint = (process.env.R2_ENDPOINT || '').replace(/\/+$/, '').split('/').slice(0, 3).join('/')
  const r2 = new AwsClient({
    accessKeyId: process.env.R2_ACCESS_KEY_ID || '',
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY || '',
    service: 's3', region: 'auto',
  })
  const url = new URL(`${endpoint}/${BUCKET}/${key}`)
  url.searchParams.set('X-Amz-Expires', '600')
  const signed = await r2.sign(new Request(url), { aws: { signQuery: true } })
  return Response.redirect(signed.url, 302)
}
