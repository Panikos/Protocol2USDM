import Link from 'next/link';
import { FileText, Activity, GitBranch, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AppShell } from '@/components/ui/app-shell';

export default function HomePage() {
  return (
    <AppShell
      gradient
      headerRight={
        <nav className="flex items-center gap-4">
          <Link href="/protocols">
            <Button variant="ghost">Protocols</Button>
          </Link>
        </nav>
      }
    >

      {/* Hero section */}
      <section className="container mx-auto px-4 py-16 text-center">
        <h2 className="text-4xl font-bold tracking-tight mb-4">
          Modern USDM Protocol Viewer
        </h2>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          View, explore, and author clinical trial protocols in USDM format with
          full provenance tracking and visual editing capabilities.
        </p>
        <div className="flex items-center justify-center gap-4">
          <Link href="/protocols">
            <Button size="lg">
              <FileText className="h-5 w-5 mr-2" />
              Browse Protocols
            </Button>
          </Link>
          <Link href="/docs">
            <Button variant="outline" size="lg">
              Learn More
            </Button>
          </Link>
        </div>
      </section>

      {/* Features grid */}
      <section className="container mx-auto px-4 py-12">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          <FeatureCard
            icon={<Activity className="h-8 w-8" />}
            title="Schedule of Activities"
            description="Interactive SoA table with AG Grid, row/column reordering, and provenance-colored cells."
          />
          <FeatureCard
            icon={<GitBranch className="h-8 w-8" />}
            title="Timeline Diagrams"
            description="Visual timeline editing with Cytoscape.js, drag-and-drop node positioning, and snap-to-grid."
          />
          <FeatureCard
            icon={<Clock className="h-8 w-8" />}
            title="Provenance Tracking"
            description="Full extraction provenance with text/vision source tracking and PDF reference linking."
          />
          <FeatureCard
            icon={<FileText className="h-8 w-8" />}
            title="Draft/Publish Workflow"
            description="Author layout changes with draft/publish workflow and version control."
          />
        </div>
      </section>

      {/* Quick start */}
      <section className="container mx-auto px-4 py-12">
        <Card>
          <CardHeader>
            <CardTitle>Quick Start</CardTitle>
            <CardDescription>
              Get started by selecting a protocol from the list or running the extraction pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 border rounded-lg">
                <h4 className="font-semibold mb-2">1. Select Protocol</h4>
                <p className="text-sm text-muted-foreground">
                  Browse available protocol extractions from the output directory.
                </p>
              </div>
              <div className="p-4 border rounded-lg">
                <h4 className="font-semibold mb-2">2. View SoA & Timeline</h4>
                <p className="text-sm text-muted-foreground">
                  Explore the Schedule of Activities table and timeline diagram.
                </p>
              </div>
              <div className="p-4 border rounded-lg">
                <h4 className="font-semibold mb-2">3. Author & Publish</h4>
                <p className="text-sm text-muted-foreground">
                  Customize layout, save drafts, and publish your changes.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          Protocol2USDM | USDM v4.0 Format
        </div>
      </footer>
    </AppShell>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <Card className="text-center">
      <CardHeader>
        <div className="mx-auto mb-2 h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}
