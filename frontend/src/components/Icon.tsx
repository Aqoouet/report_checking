interface IconProps {
  name: string;
  className?: string;
  title?: string;
}

export function Icon({ name, className, title }: IconProps) {
  return (
    <svg
      className={className}
      aria-hidden={title ? undefined : "true"}
      role={title ? "img" : undefined}
    >
      {title ? <title>{title}</title> : null}
      <use href={`/icons.svg#${name}`} />
    </svg>
  );
}
