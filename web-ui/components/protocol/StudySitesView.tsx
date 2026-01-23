'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { 
  MapPin, 
  Building2,
  Globe,
  Users,
  Hash,
  CheckCircle,
  XCircle,
  Clock,
  Info,
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
  address?: string | { line?: string; city?: string; state?: string; postalCode?: string; country?: string };
  organization?: { name?: string };
  organizationId?: string;
  siteNumber?: string;
  status?: string;
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

  // Get geographic scope from top-level
  const geographicScope = usdm.geographicScope as { type?: { decode?: string }; regions?: string[] } | undefined;
  const countriesList = (usdm.countries as { name?: string; code?: string; decode?: string }[]) ?? [];

  // Get countries from sites (fallback)
  const countriesFromSites = [...new Set(
    studySites
      .map(site => site.country)
      .filter(Boolean)
  )];
  
  // Use countries list if available, otherwise derive from sites
  const countries = countriesList.length > 0 
    ? countriesList.map(c => c.name || c.decode || c.code || 'Unknown')
    : countriesFromSites;

  // Group sites by country for display
  const sitesByCountry = studySites.reduce((acc, site) => {
    const country = site.country || 'Unknown';
    if (!acc[country]) acc[country] = [];
    acc[country].push(site);
    return acc;
  }, {} as Record<string, StudySite[]>);

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

      {/* Geographic Scope & Distribution */}
      {(countries.length > 0 || geographicScope) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5" />
              Geographic Coverage
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {geographicScope?.type?.decode && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Scope:</span>
                <Badge variant="default">{geographicScope.type.decode}</Badge>
              </div>
            )}
            {geographicScope?.regions && geographicScope.regions.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Regions:</span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {geographicScope.regions.map((region, i) => (
                    <Badge key={i} variant="outline">{region}</Badge>
                  ))}
                </div>
              </div>
            )}
            {countries.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Countries ({countries.length}):</span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {countries.map((country, i) => {
                    const siteCount = sitesByCountry[country as string]?.length || 0;
                    return (
                      <Badge key={i} variant="secondary" className="text-sm">
                        {country} {siteCount > 0 && `(${siteCount} site${siteCount !== 1 ? 's' : ''})`}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}
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
              {studySites.map((site, i) => {
                const hasDetails = site.siteNumber || site.status || site.id || site.description || 
                  (typeof site.address === 'object' && site.address);
                
                const StatusIcon = site.status === 'Active' ? CheckCircle : 
                  site.status === 'Inactive' ? XCircle : Clock;
                const statusColor = site.status === 'Active' ? 'text-green-600' : 
                  site.status === 'Inactive' ? 'text-red-600' : 'text-yellow-600';
                
                const siteCard = (
                  <div className={`p-3 bg-muted rounded-lg ${hasDetails ? 'cursor-pointer hover:bg-muted/80 transition-colors' : ''}`}>
                    <div className="flex items-start justify-between">
                      <div className="font-medium flex items-center gap-2">
                        {site.name || `Site ${i + 1}`}
                        {hasDetails && <Info className="h-3 w-3 text-muted-foreground" />}
                      </div>
                      <div className="flex items-center gap-1">
                        {site.siteNumber && (
                          <Badge variant="outline" className="text-xs">
                            <Hash className="h-3 w-3 mr-1" />
                            {site.siteNumber}
                          </Badge>
                        )}
                        {site.status && (
                          <Badge variant={site.status === 'Active' ? 'default' : 'secondary'} className="text-xs">
                            <StatusIcon className={`h-3 w-3 mr-1 ${statusColor}`} />
                            {site.status}
                          </Badge>
                        )}
                      </div>
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
                );
                
                if (!hasDetails) {
                  return <div key={i}>{siteCard}</div>;
                }
                
                return (
                  <HoverCard key={i} openDelay={200}>
                    <HoverCardTrigger asChild>
                      {siteCard}
                    </HoverCardTrigger>
                    <HoverCardContent className="w-80" side="top">
                      <div className="space-y-3">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-semibold">{site.name || `Site ${i + 1}`}</h4>
                            {site.siteNumber && (
                              <p className="text-sm text-muted-foreground">Site #{site.siteNumber}</p>
                            )}
                          </div>
                          {site.status && (
                            <Badge variant={site.status === 'Active' ? 'default' : 'secondary'}>
                              {site.status}
                            </Badge>
                          )}
                        </div>
                        
                        <div className="space-y-2 text-sm">
                          {site.description && (
                            <div>
                              <span className="font-medium">Description:</span>
                              <p className="text-muted-foreground">{site.description}</p>
                            </div>
                          )}
                          
                          {typeof site.address === 'object' && site.address && (
                            <div>
                              <span className="font-medium">Address:</span>
                              <p className="text-muted-foreground">
                                {[site.address.line, site.address.city, site.address.state, site.address.postalCode, site.address.country]
                                  .filter(Boolean)
                                  .join(', ')}
                              </p>
                            </div>
                          )}
                          
                          {typeof site.address === 'string' && site.address && (
                            <div>
                              <span className="font-medium">Address:</span>
                              <p className="text-muted-foreground">{site.address}</p>
                            </div>
                          )}
                          
                          {site.country && (
                            <div className="flex items-center gap-2">
                              <Globe className="h-4 w-4 text-muted-foreground" />
                              <span>{site.country}</span>
                            </div>
                          )}
                          
                          {site.id && (
                            <div className="pt-2 border-t">
                              <span className="text-xs text-muted-foreground font-mono">
                                ID: {site.id.substring(0, 8)}...
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </HoverCardContent>
                  </HoverCard>
                );
              })}
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
                      <Badge variant="outline">
                        {typeof org.type === 'string' ? org.type : (org.type.decode || org.type.code || 'Unknown')}
                      </Badge>
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
