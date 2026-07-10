import { Icon } from "@/components/ui/icon";

const HIGHLIGHTS = [
  { icon: "forum", text: "Answers customers on WhatsApp 24/7" },
  { icon: "mic", text: "Understands voice notes, not just text" },
  { icon: "front_hand", text: "Hands off to you the moment it's unsure" },
];

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-10"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, white 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="relative flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15">
            <Icon name="smart_toy" size={20} />
          </div>
          <span className="text-lg font-semibold">WA Receptionist</span>
        </div>

        <div className="relative flex flex-col gap-6">
          <p className="text-2xl font-medium leading-snug">
            Your WhatsApp assistant, trained on your business, answering
            customers while you focus on running it.
          </p>
          <div className="flex flex-col gap-3">
            {HIGHLIGHTS.map((h) => (
              <div key={h.text} className="flex items-center gap-3 text-sm text-primary-foreground/90">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/10">
                  <Icon name={h.icon} size={16} />
                </div>
                {h.text}
              </div>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-primary-foreground/60">
          Missed lead recovery, not just another chatbot.
        </p>
      </div>

      <div className="flex flex-col items-center justify-center gap-8 p-6">
        <div className="flex items-center gap-2 lg:hidden">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-container text-on-primary-container">
            <Icon name="smart_toy" size={18} />
          </div>
          <span className="font-semibold text-primary">WA Receptionist</span>
        </div>
        {children}
      </div>
    </div>
  );
}
