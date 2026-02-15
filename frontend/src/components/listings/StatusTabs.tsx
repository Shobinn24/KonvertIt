import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

const statuses = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "draft", label: "Draft" },
  { value: "ended", label: "Ended" },
  { value: "error", label: "Error" },
] as const;

interface StatusTabsProps {
  value: string;
  onChange: (value: string) => void;
}

export function StatusTabs({ value, onChange }: StatusTabsProps) {
  return (
    <Tabs value={value} onValueChange={onChange}>
      <TabsList>
        {statuses.map((s) => (
          <TabsTrigger key={s.value} value={s.value}>
            {s.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
