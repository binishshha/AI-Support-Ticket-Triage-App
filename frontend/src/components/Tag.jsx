import { TICKET_PALETTE } from "../constants";

export default function Tag({ kind, value }) {
  const label = value || "Not analyzed";
  const tone = TICKET_PALETTE[kind]?.[label] ?? TICKET_PALETTE.neutral.value;

  return (
    <span
      className="tag"
      style={{ "--tag-ink": tone.ink, "--tag-wash": tone.wash }}
    >
      {label}
    </span>
  );
}
