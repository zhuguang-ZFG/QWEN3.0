## Canonical role

`donglicao-site-v2/` is the **Next.js-based iteration of the LiMa public site**. It is built as a static site (`next build`) and deployed by `.github/workflows/deploy-site-v2.yml` to the VPS path configured in `secrets.SITE_V2_DIR`.

It currently hosts:

- The new homepage and brand experience (`app/page.tsx`)
- English locale pages under `/en/`
- Blog (`app/blog/`)
- Pricing and product pages being iterated in Next.js

It does **not** yet replace `donglicao-site/` (v1 static site), which still serves the canonical product-detail pages (`product-draw.html`, `product-write.html`, `product-human.html`) and the `/` fallback `chat.html` via `routes/static_files.py`. Migrate those pages to v2 and update the fallback before archiving v1.

---

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
