'use client';

import Link from 'next/link';
import { FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ThemeToggle } from './theme-toggle';
import type { ReactNode } from 'react';

interface AppShellProps {
  children: ReactNode;
  /** Subtitle shown under the logo */
  subtitle?: string;
  /** Right-side header content */
  headerRight?: ReactNode;
  /** Additional content below the main header row (e.g., tab navigation) */
  headerBottom?: ReactNode;
  /** Whether to use a gradient background (home page) or plain */
  gradient?: boolean;
  /** Whether header should be sticky */
  sticky?: boolean;
  /** Additional className for the outer wrapper */
  className?: string;
}

export function AppShell({
  children,
  subtitle = 'USDM v4.0 Viewer & Editor',
  headerRight,
  headerBottom,
  gradient = false,
  sticky = true,
  className,
}: AppShellProps) {
  return (
    <div className={cn(
      'min-h-screen',
      gradient ? 'bg-gradient-to-b from-slate-50 to-slate-100' : 'bg-slate-50',
      className
    )}>
      {/* Skip navigation link — F14 */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2 focus:rounded-md"
      >
        Skip to main content
      </a>

      <header className={cn(
        'border-b bg-white/80 backdrop-blur-sm z-50 overflow-visible',
        sticky && 'sticky top-0'
      )}>
        <div className="container mx-auto px-4 py-3 overflow-visible">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Protocol2USDM</h1>
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              </div>
            </Link>
            <div className="flex items-center gap-2">
              {headerRight}
              <ThemeToggle />
            </div>
          </div>
        </div>
        {headerBottom}
      </header>

      <main id="main-content" className="flex-1">
        {children}
      </main>
    </div>
  );
}

export default AppShell;
