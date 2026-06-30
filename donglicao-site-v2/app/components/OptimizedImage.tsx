import { type ImgHTMLAttributes } from "react";

interface OptimizedImageProps extends ImgHTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
  fill?: boolean;
  priority?: boolean;
  sizes?: string;
}

function deriveSources(src: string) {
  const base = src.replace(/\.(webp|png|jpg|jpeg)$/i, "");
  return {
    avif: `${base}.avif`,
    webp: `${base}.webp`,
  };
}

export default function OptimizedImage({
  src,
  alt,
  fill,
  priority,
  sizes,
  className,
  ...rest
}: OptimizedImageProps) {
  const { avif, webp } = deriveSources(src);

  const img = (
    <img
      src={src}
      alt={alt}
      sizes={sizes}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      className={fill ? `absolute inset-0 h-full w-full ${className ?? ""}` : className}
      {...rest}
    />
  );

  return (
    <picture>
      <source srcSet={avif} type="image/avif" />
      <source srcSet={webp} type="image/webp" />
      {img}
    </picture>
  );
}
