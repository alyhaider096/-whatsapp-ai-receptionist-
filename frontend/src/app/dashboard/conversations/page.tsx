import { Icon } from "@/components/ui/icon";

export default function ConversationsEmptyState() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-on-surface-variant">
      <Icon name="forum" size={40} />
      <p className="text-sm">Select a conversation to view the thread.</p>
    </div>
  );
}
