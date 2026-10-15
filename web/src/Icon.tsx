const paths = {
  home: 'M3 10 12 3l9 7v11h-7v-7h-4v7H3z',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  settings: 'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
  layers: 'm12 3 10 5-10 5L2 8z M2 12l10 5 10-5 M2 16l10 5 10-5',
  pause: 'M8 5v14 M16 5v14',
  play: 'm8 4 12 8-12 8z',
  sun: 'M12 3v2 M12 19v2 M3 12h2 M19 12h2 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2 M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  moon: 'M20 14A9 9 0 0 1 10 4a9 9 0 1 0 10 10z',
  monitor: 'M3 4h18v13H3z M8 21h8 M12 17v4',
  queue: 'M4 4h16v16H4z M8 8h8 M8 12h8 M8 16h5',
  proof: 'M6 3h8l4 4v14H6z M14 3v5h5 M9 12h6 M9 16h6',
  check: 'm5 12 4 4 10-10',
  arrow: 'M5 12h14 m-5-5 5 5-5 5',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-1l2 6 M4 12l2 6a7 7 0 0 0 12-1',
  shield: 'm12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z m-4 9 3 3 5-5',
  search: 'M16 16l5 5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  close: 'm6 6 12 12 M6 18 18 6',
  edit: 'm15 4 5 5 M4 20l5-1L21 7l-5-5L4 14z',
  clock: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 7v5l4 2',
  upload: 'M12 16V3 m-5 5 5-5 5 5 M4 15v6h16v-6',
  chevron: 'm9 5 7 7-7 7',
  bolt: 'm13 2-9 12h7l-1 8 10-12h-7z',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v6 M12 7v1',
  external: 'M14 3h7v7 M21 3 10 14 M10 3H3v18h18v-7',
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
