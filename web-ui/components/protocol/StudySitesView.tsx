'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card';
import { EditableField } from '@/components/semantic';
import { EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic/EditableCodedValue';
import { designPath, versionPath } from '@/lib/semantic/schema';
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
  label?: string;
  description?: string;
  country?: string | { code?: string; decode?: string; codeSystem?: string };
  extensionAttributes?: { url?: string; valueString?: string }[];
  instanceType?: string;
}

interface Organization {
  id: string;
  name?: string;
  type?: string | { decode?: string; code?: string };
  identifier?: string;
  identifierScheme?: string;
  legalAddress?: { country?: string | { decode?: string }; city?: string; text?: string };
  managedSites?: StudySite[];
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

  // Get organizations (per USDM v4.0, sites live inside Organization.managedSites[])
  const organizations = (version?.organizations as Organization[]) ?? [];

  // Collect all StudySites from Organization.managedSites[]
  const studySites: StudySite[] = [];
  for (const org of organizations) {
    if (org.managedSites) {
      studySites.push(...org.managedSites);
    }
  }

  // Helper: resolve country display string from Code object or string
  const getCountryName = (site: StudySite): string => {
    if (!site.country) return 'Unknown';
    if (typeof site.country === 'string') return site.country;
    return site.country.decode || site.country.code || 'Unknown';
  };

  // Helper: get extension attribute value
  const getExtension = (site: StudySite, urlSuffix: string): string | undefined => {
    return site.extensionAttributes?.find(e => e.url?.endsWith(urlSuffix))?.valueString;
  };

  // Get geographic scope from top-level
  const geographicScope = usdm.geographicScope as { type?: { decode?: string }; regions?: string[] } | undefined;
  const countriesList = (usdm.countries as { name?: string; code?: string; decode?: string }[]) ?? [];

  // Get countries from sites (fallback)
  const countriesFromSites = [...new Set(
    studySites.map(s => getCountryName(s)).filter(c => c !== 'Unknown')
  )];

  // Use countries list if available, otherwise derive from sites
  const countries = countriesList.length > 0
    ? countriesList.map(c => c.name || c.decode || c.code || 'Unknown')
    : countriesFromSites;

  // Group sites by country for display
  const sitesByCountry = studySites.reduce((acc, site) => {
    const country = getCountryName(site);
    if (!acc[country]) acc[country] = [];
    acc[country].push(site);
    return acc;
  }, {} as Record<string, StudySite[]>);

  // Get planned enrollment from population
  const population = studyDesign.population as Record<string, unknown> | undefined;
  const enrollmentRange = population?.plannedEnrollmentNumber as {
    minValue?: { value?: number };
    maxValue?: { value?: number };
    isApproximate?: boolean;
  } | undefined;
  const enrollmentNumber = enrollmentRange?.maxValue?.value ?? enrollmentRange?.minValue?.value;
  const enrollmentDisplay = enrollmentNumber
    ? `${enrollmentRange?.isApproximate ? '~' : ''}${enrollmentNumber.toLocaleString()}`
    : '-';

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
                <div className="text-2xl font-bold">{enrollmentDisplay}</div>
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
                const siteNumber = getExtension(site, 'siteNumber');
                const siteStatus = getExtension(site, 'status');
                const countryName = getCountryName(site);
                const hasDetails = siteNumber || siteStatus || site.id || site.description;
                
                const StatusIcon = siteStatus === 'Active' ? CheckCircle : 
                  siteStatus === 'Inactive' ? XCircle : Clock;
                const statusColor = siteStatus === 'Active' ? 'text-green-600' : 
                  siteStatus === 'Inactive' ? 'text-red-600' : 'text-yellow-600';
                
                const siteCard = (
                  <div className={`p-3 bg-muted rounded-lg ${hasDetails ? 'cursor-pointer hover:bg-muted/80 transition-colors' : ''}`}>
                    <div className="flex items-start justify-between">
                      <div className="font-medium flex items-center gap-2" onClick={e => e.stopPropagation()}>
                        <EditableField
                          path={`/study/versions/0/organizations/*/managedSites/${site.id}/name`}
                          value={site.name || `Site ${i + 1}`}
                          placeholder="Site name"
                        />
                        {hasDetails && <Info className="h-3 w-3 text-muted-foreground" />}
                      </div>
                      <div className="flex items-center gap-1">
                        {siteNumber && (
                          <Badge variant="outline" className="text-xs">
                            <Hash className="h-3 w-3 mr-1" />
                            {siteNumber}
                          </Badge>
                        )}
                        {siteStatus && (
                          <Badge variant={siteStatus === 'Active' ? 'default' : 'secondary'} className="text-xs">
                            <StatusIcon className={`h-3 w-3 mr-1 ${statusColor}`} />
                            {siteStatus}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                      {countryName !== 'Unknown' && <span>{countryName}</span>}
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
                            {siteNumber && (
                              <p className="text-sm text-muted-foreground">Site #{siteNumber}</p>
                            )}
                          </div>
                          {siteStatus && (
                            <Badge variant={siteStatus === 'Active' ? 'default' : 'secondary'}>
                              {siteStatus}
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
                          
                          {countryName !== 'Unknown' && (
                            <div className="flex items-center gap-2">
                              <Globe className="h-4 w-4 text-muted-foreground" />
                              <span>{countryName}</span>
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
                <div key={org.id || i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <EditableField
                      path={org.id ? versionPath('organizations', org.id, 'name') : `/study/versions/0/organizations/${i}/name`}
                      value={org.name || `Organization ${i + 1}`}
                      className="font-medium"
                      placeholder="Organization name"
                    />
                    <EditableCodedValue
                      path={org.id ? versionPath('organizations', org.id, 'type') : `/study/versions/0/organizations/${i}/type`}
                      value={typeof org.type === 'string' ? { decode: org.type } : org.type}
                      options={CDISC_TERMINOLOGIES.organizationType ?? []}
                      showCode
                      placeholder="Type"
                    />
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
