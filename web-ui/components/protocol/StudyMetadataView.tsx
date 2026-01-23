'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Building2, Calendar, FlaskConical, Users, FileText, BookOpen, ChevronDown, ChevronRight, Globe, Tag } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StudyMetadataViewProps {
  usdm: Record<string, unknown> | null;
}

interface StudyTitle {
  text: string;
  type?: { decode?: string };
}

interface StudyIdentifier {
  text: string;
  scopeId?: string;
}

interface Organization {
  id: string;
  name: string;
  type?: { decode?: string };
}

interface Abbreviation {
  id?: string;
  abbreviatedText: string;
  expandedText: string;
}

interface Characteristic {
  id?: string;
  name?: string;
  text?: string;
  value?: string;
}

export function StudyMetadataView({ usdm }: StudyMetadataViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract study version data
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  
  if (!version) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No study version found</p>
        </CardContent>
      </Card>
    );
  }

  // Extract titles
  const titles = (version.titles as StudyTitle[]) ?? [];
  const officialTitle = titles.find(t => t.type?.decode?.includes('Official'))?.text;
  const briefTitle = titles.find(t => t.type?.decode?.includes('Brief'))?.text;
  const acronym = titles.find(t => t.type?.decode?.includes('Acronym'))?.text;

  // Extract identifiers
  const identifiers = (version.studyIdentifiers as StudyIdentifier[]) ?? [];
  
  // Extract study design info
  const studyDesigns = (version.studyDesigns as Record<string, unknown>[]) ?? [];
  const design = studyDesigns[0];
  
  const studyPhase = (design?.studyPhase as { standardCode?: { decode?: string } })?.standardCode?.decode;
  const studyType = (design?.studyType as { decode?: string })?.decode;
  const therapeuticAreas = (design?.therapeuticAreas as { decode?: string }[]) ?? [];
  const blindingSchema = (design?.blindingSchema as { standardCode?: { decode?: string } })?.standardCode?.decode;
  
  // Extract organizations
  const organizations = (version.organizations as Organization[]) ?? [];
  const sponsor = organizations.find(o => o.type?.decode?.includes('Sponsor'));

  // Extract dates
  const dateValues = (version.dateValues as { name?: string; dateValue?: string; type?: { decode?: string } }[]) ?? [];

  // Extract abbreviations
  const abbreviations = (version.abbreviations as Abbreviation[]) ?? [];

  // Extract characteristics
  const characteristics = (design?.characteristics as Characteristic[]) ?? [];

  // Extract conditions (medical conditions)
  const conditions = (version.conditions as { name?: string; description?: string; codes?: { decode?: string }[] }[]) ?? [];

  // State for collapsible sections
  const [showAllAbbreviations, setShowAllAbbreviations] = useState(false);
  const [showAllOrgs, setShowAllOrgs] = useState(false);

  // Sort abbreviations alphabetically
  const sortedAbbreviations = [...abbreviations].sort((a, b) => 
    (a.abbreviatedText || '').localeCompare(b.abbreviatedText || '')
  );
  const displayedAbbreviations = showAllAbbreviations ? sortedAbbreviations : sortedAbbreviations.slice(0, 10);

  // Categorize organizations
  const sponsors = organizations.filter(o => o.type?.decode?.toLowerCase().includes('sponsor'));
  const cros = organizations.filter(o => o.type?.decode?.toLowerCase().includes('cro') || o.type?.decode?.toLowerCase().includes('contract'));
  const otherOrgs = organizations.filter(o => !sponsors.includes(o) && !cros.includes(o));
  const displayedOrgs = showAllOrgs ? organizations : [...sponsors, ...cros].slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Study Identification */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Study Identification
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {acronym && (
            <div>
              <span className="text-sm text-muted-foreground">Acronym</span>
              <p className="text-lg font-semibold">{acronym}</p>
            </div>
          )}
          
          {officialTitle && (
            <div>
              <span className="text-sm text-muted-foreground">Official Title</span>
              <p className="text-base">{officialTitle}</p>
            </div>
          )}
          
          {briefTitle && briefTitle !== officialTitle && (
            <div>
              <span className="text-sm text-muted-foreground">Brief Title</span>
              <p className="text-base">{briefTitle}</p>
            </div>
          )}

          {identifiers.length > 0 && (
            <div>
              <span className="text-sm text-muted-foreground">Identifiers</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {identifiers.map((id, i) => {
                  const idType = id.identifierType?.decode || id.identifierType?.code || '';
                  const isNCT = idType.includes('NCT') || id.text?.startsWith('NCT');
                  const isEudraCT = idType.includes('EudraCT') || /^\d{4}-\d{6}-\d{2}$/.test(id.text || '');
                  return (
                    <div key={i} className="flex items-center gap-1">
                      <Badge 
                        variant={isNCT ? 'default' : isEudraCT ? 'outline' : 'secondary'}
                        className={isNCT ? 'bg-blue-600' : ''}
                      >
                        {idType && <span className="opacity-70 mr-1">{idType}:</span>}
                        {id.text}
                      </Badge>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Study Design */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Study Design
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {studyPhase && (
              <div>
                <span className="text-sm text-muted-foreground">Phase</span>
                <p className="font-medium">{studyPhase}</p>
              </div>
            )}
            
            {studyType && (
              <div>
                <span className="text-sm text-muted-foreground">Type</span>
                <p className="font-medium">{studyType}</p>
              </div>
            )}
            
            {blindingSchema && (
              <div>
                <span className="text-sm text-muted-foreground">Blinding</span>
                <p className="font-medium">{blindingSchema}</p>
              </div>
            )}

            {therapeuticAreas.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Therapeutic Area</span>
                <p className="font-medium">{therapeuticAreas[0]?.decode ?? 'N/A'}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Organizations - Collapsible */}
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
              {displayedOrgs.map((org, i) => {
                const orgType = org.type?.decode || org.type?.code || 'Organization';
                const isSponsor = orgType.toLowerCase().includes('sponsor');
                const isCRO = orgType.toLowerCase().includes('cro') || orgType.toLowerCase().includes('contract');
                return (
                  <div key={i} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <p className="font-medium">{org.name}</p>
                      {org.identifier && (
                        <p className="text-xs text-muted-foreground">{org.identifier}</p>
                      )}
                    </div>
                    <Badge 
                      variant={isSponsor ? 'default' : isCRO ? 'outline' : 'secondary'}
                      className={isSponsor ? 'bg-green-600' : ''}
                    >
                      {orgType}
                    </Badge>
                  </div>
                );
              })}
            </div>
            {organizations.length > 5 && (
              <button
                onClick={() => setShowAllOrgs(!showAllOrgs)}
                className="mt-4 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                {showAllOrgs ? (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronRight className="h-4 w-4" />
                    Show all {organizations.length} organizations
                  </>
                )}
              </button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Key Dates */}
      {dateValues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Key Dates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {dateValues.map((dv, i) => (
                <div key={i}>
                  <span className="text-sm text-muted-foreground">
                    {dv.type?.decode ?? dv.name ?? 'Date'}
                  </span>
                  <p className="font-medium">{dv.dateValue ?? 'N/A'}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Population Summary */}
      {design?.population && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Population
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(design.population as Record<string, unknown>)?.description && (
                <p>{String((design.population as Record<string, unknown>).description)}</p>
              )}
              <div className="flex gap-4 text-sm">
                {(design.population as Record<string, unknown>)?.plannedEnrollmentNumber && (
                  <span>
                    <strong>Planned Enrollment:</strong>{' '}
                    {String(((design.population as Record<string, unknown>).plannedEnrollmentNumber as Record<string, unknown>)?.value ?? 'N/A')}
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Medical Conditions */}
      {conditions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Tag className="h-5 w-5" />
              Medical Conditions
              <Badge variant="secondary">{conditions.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {conditions.map((cond, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="font-medium">{cond.name || `Condition ${i + 1}`}</div>
                  {cond.description && (
                    <p className="text-sm text-muted-foreground mt-1">{cond.description}</p>
                  )}
                  {cond.codes && cond.codes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {cond.codes.map((code, j) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {code.decode}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Study Characteristics */}
      {characteristics.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Tag className="h-5 w-5" />
              Study Characteristics
              <Badge variant="secondary">{characteristics.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {characteristics.map((char, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="font-medium text-sm text-muted-foreground">
                    {char.name || `Characteristic ${i + 1}`}
                  </div>
                  <div className="mt-1">{char.text || char.value || 'N/A'}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Abbreviations - Collapsible */}
      {abbreviations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5" />
              Abbreviations Glossary
              <Badge variant="secondary">{abbreviations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {displayedAbbreviations.map((abbr, i) => (
                <div key={i} className="flex items-start gap-2 p-2 rounded hover:bg-muted">
                  <Badge variant="outline" className="shrink-0 font-mono">
                    {abbr.abbreviatedText}
                  </Badge>
                  <span className="text-sm text-muted-foreground">{abbr.expandedText}</span>
                </div>
              ))}
            </div>
            {abbreviations.length > 10 && (
              <button
                onClick={() => setShowAllAbbreviations(!showAllAbbreviations)}
                className="mt-4 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                {showAllAbbreviations ? (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronRight className="h-4 w-4" />
                    Show all {abbreviations.length} abbreviations
                  </>
                )}
              </button>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default StudyMetadataView;
