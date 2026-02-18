'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField, EditableList, CodeLink } from '@/components/semantic';
import { EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic/EditableCodedValue';
import { versionPath } from '@/lib/semantic/schema';
import { Building2, Calendar, FlaskConical, Users, FileText, BookOpen, ChevronDown, ChevronRight, Globe, Tag, ExternalLink } from 'lucide-react';
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
  code?: string;
  codeSystem?: string;
  decode?: string;
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
  const therapeuticAreas = (design?.therapeuticAreas as { code?: string; codeSystem?: string; decode?: string }[]) ?? [];
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

  // Extract randomization from subTypes[] (USDM v4.0 stores randomization as a Code in subTypes)
  const RANDOMIZATION_CODES = new Set(['C25196', 'C48660']);
  const subTypes = (design?.subTypes as { code?: string; decode?: string }[]) ?? [];
  const randomizationEntry = subTypes.find(st => st.code && RANDOMIZATION_CODES.has(st.code));
  const randomizationIndex = subTypes.findIndex(st => st.code && RANDOMIZATION_CODES.has(st.code));

  // Extract indications (medical conditions) from studyDesign — USDM v4.0 correct path
  const indications = (design?.indications as { id?: string; name?: string; description?: string; codes?: { decode?: string; code?: string; codeSystem?: string }[] }[]) ?? [];

  // State for collapsible sections
  const [showAllOrgs, setShowAllOrgs] = useState(false);

  // Sort abbreviations alphabetically
  const sortedAbbreviations = [...abbreviations].sort((a, b) => 
    (a.abbreviatedText || '').localeCompare(b.abbreviatedText || '')
  );

  // Categorize organizations
  const sponsors = organizations.filter(o => o.type?.decode?.toLowerCase().includes('sponsor'));
  const cros = organizations.filter(o => o.type?.decode?.toLowerCase().includes('cro') || o.type?.decode?.toLowerCase().includes('contract'));
  const otherOrgs = organizations.filter(o => !sponsors.includes(o) && !cros.includes(o));
  const displayedOrgs = showAllOrgs ? organizations : [...sponsors, ...cros].slice(0, 5);

  // Stats counts
  const activities = (design?.activities as unknown[]) ?? [];
  const encounters = (design?.encounters as unknown[]) ?? [];
  const epochs = (design?.epochs as unknown[]) ?? [];
  const arms = (design?.arms as unknown[]) ?? [];

  const stats = [
    { label: 'Activities', value: activities.length },
    { label: 'Encounters', value: encounters.length },
    { label: 'Epochs', value: epochs.length },
    { label: 'Arms', value: arms.length },
  ];

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-6">
              <p className="text-3xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

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
            <div>
              <EditableCodedValue
                path="/study/versions/0/studyDesigns/0/studyPhase/standardCode"
                value={(design?.studyPhase as Record<string, unknown>)?.standardCode as { code?: string; decode?: string } | undefined}
                label="Phase"
                options={CDISC_TERMINOLOGIES.studyPhase ?? []}
                showCode
                placeholder="Not specified"
              />
            </div>
            
            <div>
              <EditableCodedValue
                path="/study/versions/0/studyDesigns/0/studyType"
                value={design?.studyType as { code?: string; decode?: string } | undefined}
                label="Type"
                options={CDISC_TERMINOLOGIES.studyType ?? []}
                showCode
                placeholder="Not specified"
              />
            </div>
            
            <div>
              <EditableCodedValue
                path="/study/versions/0/studyDesigns/0/blindingSchema/standardCode"
                value={(design?.blindingSchema as Record<string, unknown>)?.standardCode as { code?: string; decode?: string } | undefined}
                label="Blinding"
                options={CDISC_TERMINOLOGIES.blindingSchema ?? []}
                showCode
                placeholder="Not specified"
              />
            </div>

            <div>
              <EditableCodedValue
                path={randomizationIndex >= 0 ? `/study/versions/0/studyDesigns/0/subTypes/${randomizationIndex}` : '/study/versions/0/studyDesigns/0/subTypes/0'}
                value={randomizationEntry}
                label="Randomization"
                options={CDISC_TERMINOLOGIES.randomizationType ?? []}
                showCode
                placeholder="Not specified"
              />
            </div>

            {therapeuticAreas.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Therapeutic Area</span>
                <div className="flex items-center gap-2">
                  <EditableField
                    path="/study/versions/0/studyDesigns/0/therapeuticAreas/0/decode"
                    value={therapeuticAreas[0]?.decode ?? ''}
                    className="font-medium"
                    placeholder="Not specified"
                  />
                  {therapeuticAreas[0]?.code && (
                    <a
                      href={`https://meshb.nlm.nih.gov/record/ui?ui=${therapeuticAreas[0].code}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 hover:underline font-mono shrink-0"
                      title="View in NLM MeSH Browser"
                    >
                      {therapeuticAreas[0].code}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                </div>
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
                        path={versionPath('organizations', org.id, 'name')}
                        value={org.name}
                        className="font-medium"
                        placeholder="Organization name"
                      />
                      {org.identifier && (
                        <EditableField
                          path={versionPath('organizations', org.id, 'identifier')}
                          value={org.identifier}
                          className="text-xs text-muted-foreground"
                          placeholder="Identifier"
                        />
                      )}
                    </div>
                    <EditableCodedValue
                      path={org.id ? versionPath('organizations', org.id, 'type') : `/study/versions/0/organizations/${orgIndex}/type`}
                      value={org.type}
                      options={CDISC_TERMINOLOGIES.organizationType ?? []}
                      showCode
                      placeholder="Type"
                    />
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
      {!!design?.population && (() => {
        const pop = design.population as Record<string, unknown>;
        const enrollment = pop.plannedEnrollmentNumber as Record<string, unknown> | undefined;
        const completion = pop.plannedCompletionNumber as Record<string, unknown> | undefined;
        const plannedAge = pop.plannedAge as Record<string, unknown> | undefined;
        const ageMin = plannedAge?.minValue as Record<string, unknown> | undefined;
        const ageMax = plannedAge?.maxValue as Record<string, unknown> | undefined;
        const plannedSex = pop.plannedSex as { code?: string; decode?: string }[] | undefined;
        const healthySubjects = pop.includesHealthySubjects;
        const popPath = '/study/versions/0/studyDesigns/0/population';

        return (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Population
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <EditableField
                  path={`${popPath}/name`}
                  value={String(pop.name ?? '')}
                  label="Name"
                  placeholder="e.g. Study Population"
                />
                <EditableField
                  path={`${popPath}/description`}
                  value={String(pop.description ?? '')}
                  label="Description"
                  type="textarea"
                  placeholder="No population description"
                />

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <EditableField
                    path={`${popPath}/plannedEnrollmentNumber/maxValue/value`}
                    value={String((enrollment?.maxValue as Record<string, unknown>)?.value ?? (enrollment as Record<string, unknown>)?.value ?? '')}
                    label="Planned Enrollment"
                    type="number"
                    placeholder="N/A"
                  />
                  <EditableField
                    path={`${popPath}/plannedCompletionNumber/maxValue/value`}
                    value={String((completion?.maxValue as Record<string, unknown>)?.value ?? (completion as Record<string, unknown>)?.value ?? '')}
                    label="Planned Completers"
                    type="number"
                    placeholder="N/A"
                  />
                  <EditableField
                    path={`${popPath}/plannedAge/minValue/value`}
                    value={String(ageMin?.value ?? '')}
                    label="Minimum Age"
                    type="number"
                    placeholder="N/A"
                  />
                  <EditableField
                    path={`${popPath}/plannedAge/maxValue/value`}
                    value={String(ageMax?.value ?? '')}
                    label="Maximum Age"
                    type="number"
                    placeholder="N/A"
                  />
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  {plannedSex && plannedSex.length > 0 ? (
                    <div>
                      <span className="text-sm text-muted-foreground">Planned Sex</span>
                      <div className="flex gap-1 mt-1">
                        {plannedSex.map((s, si) => (
                          <CodeLink key={si} code={s.code} decode={s.decode || s.code} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <EditableField
                      path={`${popPath}/plannedSex`}
                      value=""
                      label="Planned Sex"
                      placeholder="Not specified"
                    />
                  )}
                  <div>
                    <span className="text-sm text-muted-foreground">Healthy Subjects</span>
                    <div className="mt-1">
                      <Badge variant={healthySubjects ? 'default' : 'outline'}>
                        {healthySubjects === true ? 'Yes' : healthySubjects === false ? 'No' : 'Not specified'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })()}

      {/* Medical Conditions (from studyDesign.indications — USDM v4.0) */}
      <EditableList
        basePath="/study/versions/0/studyDesigns/0/indications"
        items={indications}
        title="Medical Conditions"
        icon={<Tag className="h-5 w-5" />}
        addLabel="Add Condition"
        newItemTemplate={{
          name: '',
          description: '',
          instanceType: 'Indication',
        }}
        itemDescriptor={{
          labelKey: 'name',
          subtitleKey: 'description',
          render: (item, index, itemPath) => {
            const ind = (item ?? {}) as { id?: string; name?: string; description?: string; codes?: { decode?: string; code?: string; codeSystem?: string }[] };
            return (
              <div className="flex-1 min-w-0">
                <EditableField
                  path={`${itemPath}/name`}
                  value={ind.name || `Condition ${index + 1}`}
                  label=""
                  className="font-medium"
                  placeholder="Condition name"
                />
                <EditableField
                  path={`${itemPath}/description`}
                  value={ind.description || ''}
                  label=""
                  type="textarea"
                  className="text-sm text-muted-foreground mt-1"
                  placeholder="No description"
                />
                {ind.codes && ind.codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {ind.codes.map((code: { code?: string; decode?: string; codeSystem?: string }, j: number) => (
                      <CodeLink key={j} code={code.code} decode={code.decode} codeSystem={code.codeSystem} className="text-xs" />
                    ))}
                  </div>
                )}
              </div>
            );
          },
        }}
      />

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
            <div className="flex flex-wrap gap-2">
              {characteristics.map((char, i) => (
                <Badge key={i} variant="outline" className="text-sm py-1.5 px-3">
                  {char.decode || char.name || char.code || char.text || char.value || `Characteristic ${i + 1}`}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Abbreviations */}
      <EditableList
        basePath="/study/versions/0/abbreviations"
        items={sortedAbbreviations}
        title="Abbreviations Glossary"
        icon={<BookOpen className="h-5 w-5" />}
        collapsible={sortedAbbreviations.length > 10}
        addLabel="Add Abbreviation"
        newItemTemplate={{
          abbreviatedText: '',
          expandedText: '',
          instanceType: 'Abbreviation',
        }}
        itemDescriptor={{
          labelKey: 'abbreviatedText',
          subtitleKey: 'expandedText',
          render: (item, index, itemPath) => {
            const abbr = (item ?? {}) as Abbreviation;
            return (
              <div className="flex items-start gap-2 flex-1 min-w-0">
                <EditableField
                  path={`${itemPath}/abbreviatedText`}
                  value={abbr.abbreviatedText}
                  label=""
                  className="shrink-0 font-mono text-xs border rounded px-1"
                  placeholder="ABBR"
                />
                <EditableField
                  path={`${itemPath}/expandedText`}
                  value={abbr.expandedText}
                  label=""
                  className="text-sm text-muted-foreground flex-1"
                  placeholder="Expansion"
                />
              </div>
            );
          },
        }}
      />
    </div>
  );
}

export default StudyMetadataView;
