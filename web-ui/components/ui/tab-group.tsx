'use client';

import { ReactNode } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TabItem {
  id: string;
  label: string;
  icon: ReactNode;
}

interface TabGroupProps {
  label: string;
  icon: ReactNode;
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  defaultExpanded?: boolean;
}

export function TabGroup({
  label,
  icon,
  tabs,
  activeTab,
  onTabChange,
}: TabGroupProps) {
  const hasActiveTab = tabs.some(tab => tab.id === activeTab);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
            hasActiveTab
              ? 'bg-background text-foreground border-b-2 border-primary'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
          )}
          aria-label={`${label} navigation group`}
        >
          {icon}
          <span>{label}</span>
          <ChevronDown className="h-3 w-3 ml-1" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={4}
          className="z-[70] min-w-[180px] bg-popover border border-border rounded-lg shadow-xl py-1 animate-in fade-in-0 zoom-in-95"
        >
          {tabs.map((tab) => (
            <DropdownMenu.Item
              key={tab.id}
              onSelect={() => onTabChange(tab.id)}
              className={cn(
                'flex items-center gap-2 px-3 py-2 text-sm transition-colors cursor-pointer outline-none',
                activeTab === tab.id
                  ? 'bg-accent text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent focus:bg-accent focus:text-foreground'
              )}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  children: ReactNode;
}

export function TabButton({ active, onClick, icon, children }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap',
        active
          ? 'bg-background text-foreground border-b-2 border-primary'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
      )}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}

export default TabGroup;
