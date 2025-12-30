'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  MapPin, 
  Building2,
  Globe,
  Users,
} from 'lucide-react';

interface StudySitesViewProps {
  usdm: Record<string, unknown> | null;
}

interface StudySite {
  id: string;
  name?: string;
  identifier?: string;
  description?: string;
  country?: string;
  region?: string;
  city?: string;
  address?: string;
  organization?: { name?: string };
  instanceType?: string;
}

interface Organization {
  id: string;
  name?: string;
  type?: string;
  identifier?: string;
  legalAddress?: { country?: string; city?: string };
  instanceType?: string;
}

export function StudySitesView({ usdm }: StudySitesViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <MapPin className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract data from USDM structure
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Get study sites
  const studySites = (studyDesign.studySites as StudySite[]) ?? 
    (version?.studySites as StudySite[]) ?? [];

  // Get organizations
  const organizations = (version?.organizations as Organization[]) ?? [];

  // Get countries from sites
  const countries = [...new Set(
    studySites
      .map(site => site.country)
      .filter(Boolean)
  )];

  const hasData = studySites.length > 0 || organizations.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <MapPin className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No study site information found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Study site and organization data will appear here when available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <MapPin className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{studySites.length}</div>
                <div className="text-xs text-muted-foreground">Study Sites</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{organizations.length}</div>
                <div className="text-xs text-muted-foreground">Organizations</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-green-600" />
              <div>
                <div className="text-2xl font-bold">{countries.length}</div>
                <div className="text-xs text-muted-foreground">Countries</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-orange-600" />
              <div>
                <div className="text-2xl font-bold">-</div>
                <div className="text-xs text-muted-foreground">Total Enrollment</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Countries */}
      {countries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Geographic Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {countries.map((country, i) => {
                const siteCount = studySites.filter(s => s.country === country).length;
                return (
                  <Badge key={i} variant="secondary" className="text-sm">
                    {country} ({siteCount} site{siteCount !== 1 ? 's' : ''})
                  </Badge>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Study Sites */}
      {studySites.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              Study Sites
              <Badge variant="secondary">{studySites.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {studySites.map((site, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="font-medium">
                      {site.name || `Site ${i + 1}`}
                    </div>
                    {site.identifier && (
                      <Badge variant="outline">{site.identifier}</Badge>
                    )}
                  </div>
                  {site.organization?.name && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {site.organization.name}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                    {site.city && <span>{site.city}</span>}
                    {site.city && site.country && <span>•</span>}
                    {site.country && <span>{site.country}</span>}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Organizations */}
      {organizations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5" />
              Organizations
              <Badge variant="secondary">{organizations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {organizations.map((org, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="font-medium">
                      {org.name || `Organization ${i + 1}`}
                    </div>
                    {org.type && (
                      <Badge variant="outline">{org.type}</Badge>
                    )}
                  </div>
                  {org.identifier && (
                    <p className="text-xs text-muted-foreground mt-1">
                      ID: {org.identifier}
                    </p>
                  )}
                  {org.legalAddress && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {[org.legalAddress.city, org.legalAddress.country]
                        .filter(Boolean)
                        .join(', ')}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default StudySitesView;
