'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
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
  identifierType?: { decode?: string; code?: string };
}

interface Organization {
  id: string;
  name: string;
  identifier?: string;
  type?: { decode?: string; code?: string };
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
          {titles.map((title, i) => {
            const titleType = title.type?.decode || 'Title';
            const isAcronym = titleType.includes('Acronym');
            const isOfficial = titleType.includes('Official');
            const isBrief = titleType.includes('Brief');
            
            // Skip brief if same as official
            if (isBrief && title.text === officialTitle) return null;
            
            return (
              <div key={i}>
                <span className="text-sm text-muted-foreground">{titleType}</span>
                <EditableField
                  path={`/study/versions/0/titles/${i}/text`}
                  value={title.text}
                  label=""
                  className={isAcronym ? 'text-lg font-semibold' : 'text-base'}
                  placeholder="Not specified"
                />
              </div>
            );
          })}

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
                      {idType && <span className="text-xs text-muted-foreground mr-1">{idType}:</span>}
                      <EditableField
                        path={`/study/versions/0/studyIdentifiers/${i}/text`}
                        value={id.text}
                        className={cn(
                          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold',
                          isNCT ? 'bg-blue-600 text-white' : isEudraCT ? 'border-current' : 'bg-secondary'
                        )}
                        placeholder="Identifier"
                      />
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
                <EditableField
                  path="/study/versions/0/studyDesigns/0/studyPhase/standardCode/decode"
                  value={studyPhase}
                  className="font-medium"
                  placeholder="Not specified"
                />
              </div>
            )}
            
            {studyType && (
              <div>
                <span className="text-sm text-muted-foreground">Type</span>
                <EditableField
                  path="/study/versions/0/studyDesigns/0/studyType/decode"
                  value={studyType}
                  className="font-medium"
                  placeholder="Not specified"
                />
              </div>
            )}
            
            {blindingSchema && (
              <div>
                <span className="text-sm text-muted-foreground">Blinding</span>
                <EditableField
                  path="/study/versions/0/studyDesigns/0/blindingSchema/standardCode/decode"
                  value={blindingSchema}
                  className="font-medium"
                  placeholder="Not specified"
                />
              </div>
            )}

            {therapeuticAreas.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Therapeutic Area</span>
                <EditableField
                  path="/study/versions/0/studyDesigns/0/therapeuticAreas/0/decode"
                  value={therapeuticAreas[0]?.decode ?? ''}
                  className="font-medium"
                  placeholder="Not specified"
                />
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
                const orgIndex = organizations.indexOf(org);
                const orgType = org.type?.decode || org.type?.code || 'Organization';
                const isSponsor = orgType.toLowerCase().includes('sponsor');
                const isCRO = orgType.toLowerCase().includes('cro') || orgType.toLowerCase().includes('contract');
                return (
                  <div key={i} className="flex items-center justify-between border-b pb-2 last:border-0">
                    <div>
                      <EditableField
                        path={`/study/versions/0/organizations/${orgIndex}/name`}
                        value={org.name}
                        className="font-medium"
                        placeholder="Organization name"
                      />
                      {org.identifier && (
                        <EditableField
                          path={`/study/versions/0/organizations/${orgIndex}/identifier`}
                          value={org.identifier}
                          className="text-xs text-muted-foreground"
                          placeholder="Identifier"
                        />
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
                  <EditableField
                    path={`/study/versions/0/dateValues/${i}/dateValue`}
                    value={dv.dateValue ?? ''}
                    className="font-medium"
                    placeholder="N/A"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Population Summary */}
      {!!design?.population && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Population
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <EditableField
                path="/study/versions/0/studyDesigns/0/population/description"
                value={String((design.population as Record<string, unknown>)?.description ?? '')}
                label="Description"
                type="textarea"
                placeholder="No population description"
              />
              <div className="flex gap-4 text-sm">
                {!!(design.population as Record<string, unknown>)?.plannedEnrollmentNumber && (
                  <EditableField
                    path="/study/versions/0/studyDesigns/0/population/plannedEnrollmentNumber/value"
                    value={String(((design.population as Record<string, unknown>).plannedEnrollmentNumber as Record<string, unknown>)?.value ?? '')}
                    label="Planned Enrollment"
                    type="number"
                    placeholder="N/A"
                  />
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
                  <EditableField
                    path={`/study/versions/0/conditions/${i}/name`}
                    value={cond.name || `Condition ${i + 1}`}
                    label=""
                    className="font-medium"
                    placeholder="Condition name"
                  />
                  <EditableField
                    path={`/study/versions/0/conditions/${i}/description`}
                    value={cond.description || ''}
                    label=""
                    type="textarea"
                    className="text-sm text-muted-foreground mt-1"
                    placeholder="No description"
                  />
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
              {displayedAbbreviations.map((abbr, i) => {
                // Find original index in unsorted array
                const originalIndex = abbreviations.findIndex(a => a.abbreviatedText === abbr.abbreviatedText);
                const pathIndex = originalIndex >= 0 ? originalIndex : i;
                return (
                  <div key={i} className="flex items-start gap-2 p-2 rounded hover:bg-muted">
                    <EditableField
                      path={`/study/versions/0/abbreviations/${pathIndex}/abbreviatedText`}
                      value={abbr.abbreviatedText}
                      label=""
                      className="shrink-0 font-mono text-xs border rounded px-1"
                      placeholder="ABBR"
                    />
                    <EditableField
                      path={`/study/versions/0/abbreviations/${pathIndex}/expandedText`}
                      value={abbr.expandedText}
                      label=""
                      className="text-sm text-muted-foreground flex-1"
                      placeholder="Expansion"
                    />
                  </div>
                );
              })}
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
