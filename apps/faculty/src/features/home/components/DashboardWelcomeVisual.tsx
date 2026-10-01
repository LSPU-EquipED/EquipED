/** Layered module and review sheet; decorative, without sample scores. */
export function DashboardWelcomeVisual() {
  return (
    <svg
      viewBox="0 0 320 176"
      fill="none"
      aria-hidden="true"
      className="h-auto w-full text-primary"
    >
      <path d="M24 158H300" className="stroke-primary/15" />
      <path
        d="M38 49C74 40 105 45 135 61C163 45 190 43 221 49V131C190 125 163 127 135 143C105 127 74 122 38 131V49Z"
        transform="translate(0 8)"
        className="fill-primary/10"
      />
      <path
        d="M38 49C74 40 105 45 135 61C163 45 190 43 221 49V131C190 125 163 127 135 143C105 127 74 122 38 131V49Z"
        transform="translate(0 4)"
        className="fill-primary-soft stroke-primary/45"
        strokeWidth="1.5"
      />
      <path
        d="M38 49C74 40 105 45 135 61V143C105 127 74 122 38 131V49Z"
        className="fill-surface stroke-primary/55"
        strokeWidth="1.5"
      />
      <path
        d="M135 61C163 45 190 43 221 49V131C190 125 163 127 135 143V61Z"
        className="fill-surface stroke-primary/55"
        strokeWidth="1.5"
      />
      <path
        d="M127 57L135 61L143 57V139L135 143L127 139V57Z"
        className="fill-primary/10"
      />
      <path
        d="M64 47L76 47V76L70 71L64 76V47Z"
        className="fill-accent stroke-warning/40"
      />
      <path
        d="M135 64V142M52 69C72 65 94 68 119 79M52 81C74 77 96 82 119 91M52 104C74 100 96 105 119 114M52 116C74 112 88 114 105 121"
        className="stroke-primary/40"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M47 45V37C80 31 109 39 135 56"
        className="stroke-primary/35"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <rect
        x="192"
        y="35"
        width="94"
        height="120"
        rx="5"
        className="fill-primary/10"
      />
      <rect
        x="186"
        y="28"
        width="94"
        height="120"
        rx="5"
        className="fill-surface stroke-primary/55"
        strokeWidth="1.5"
      />
      <rect
        x="215"
        y="20"
        width="36"
        height="15"
        rx="3"
        className="fill-primary stroke-primary"
        strokeWidth="1.5"
      />
      <path
        d="M202 52H260"
        className="stroke-primary/55"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {[70, 94, 118].map((y) => (
        <g key={y}>
          <rect
            x="202"
            y={y}
            width="10"
            height="10"
            rx="2"
            className="fill-primary-soft stroke-primary/45"
          />
          <path
            d={`M223 ${y + 3}H262M223 ${y + 9}H247`}
            className="stroke-primary/45"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </g>
      ))}
      <path
        d="M165 91H177M173 87L177 91L173 95"
        className="stroke-primary/50"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
