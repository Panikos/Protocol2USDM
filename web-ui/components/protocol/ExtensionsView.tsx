'use client';

import { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Puzzle, 
  ChevronDown, 
  ChevronRight,
  Activity,
  Calendar,
  Pill,
  GitBranch,
  FileText,
  Settings,
  AlertCircle,
  Clock,
  Users,
  Shuffle,
  Target,
  Beaker,
  CheckCircle,
  Code,
  ExternalLink,
  Table,
  Calculator,
  ClipboardList,
  BarChart3,
  Layers,
  FlaskConical,
  Hash,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ExtensionsViewProps {
  usdm: Record<string, unknown> | null;
}

interface ExtensionAttribute {
  id?: string;
  name?: string;
  url?: string;
  value?: unknown;
  valueString?: string;
  valueCode?: string;
  valueInteger?: number;
  valueBoolean?: boolean;
  valueQuantity?: { value: number; unit: string };
  instanceType?: string;
}

interface EntityWithExtensions {
  id?: string;
  name?: string;
  label?: string;
  instanceType?: string;
  extensionAttributes?: ExtensionAttribute[];
}

// Extension metadata for human-friendly display
const EXTENSION_METADATA: Record<string, { 
  name: string; 
  category: string; 
  icon: string;
  description: string;
}> = {
  'x-executionModel-stateMachine': { 
    name: 'State Machine', 
    category: 'Execution Model',
    icon: 'GitBranch',
    description: 'Subject state transitions through study epochs'
  },
  'x-executionModel-visitWindows': { 
    name: 'Visit Windows', 
    category: 'Execution Model',
    icon: 'Calendar',
    description: 'Allowed timing windows for each visit'
  },
  'x-executionModel-dosingRegimens': { 
    name: 'Dosing Regimens', 
    category: 'Execution Model',
    icon: 'Pill',
    description: 'Treatment dosing schedules and frequencies'
  },
  'x-executionModel-traversalConstraints': { 
    name: 'Traversal Constraints', 
    category: 'Execution Model',
    icon: 'GitBranch',
    description: 'Rules for subject flow through study'
  },
  'x-executionModel-timeAnchors': { 
    name: 'Time Anchors', 
    category: 'Execution Model',
    icon: 'Clock',
    description: 'Reference points for scheduling (First Dose, Randomization, etc.)'
  },
  'x-executionModel-repetitions': { 
    name: 'Repetitions', 
    category: 'Execution Model',
    icon: 'Activity',
    description: 'Repeated activities and their schedules'
  },
  'x-executionModel-crossoverDesign': { 
    name: 'Crossover Design', 
    category: 'Execution Model',
    icon: 'Shuffle',
    description: 'Crossover study periods and sequences'
  },
  'x-executionModel-randomizationScheme': { 
    name: 'Randomization', 
    category: 'Execution Model',
    icon: 'Users',
    description: 'Randomization method and stratification'
  },
  'x-executionModel-endpointAlgorithms': { 
    name: 'Endpoint Algorithms', 
    category: 'Execution Model',
    icon: 'Target',
    description: 'Endpoint calculation methods'
  },
  'x-executionModel-derivedVariables': { 
    name: 'Derived Variables', 
    category: 'Execution Model',
    icon: 'Beaker',
    description: 'Computed/derived data definitions'
  },
  'x-sap-derived-variables': { 
    name: 'SAP Derived Variables', 
    category: 'SAP Data',
    icon: 'Calculator',
    description: 'Calculation formulas from Statistical Analysis Plan'
  },
  'x-sap-data-handling-rules': { 
    name: 'SAP Data Handling Rules', 
    category: 'SAP Data',
    icon: 'ClipboardList',
    description: 'Missing data and BLQ handling rules from SAP'
  },
  'x-sap-statistical-methods': { 
    name: 'Statistical Methods', 
    category: 'SAP Data',
    icon: 'BarChart3',
    description: 'Primary/secondary analysis methods with STATO ontology mapping'
  },
  'x-sap-multiplicity-adjustments': { 
    name: 'Multiplicity Adjustments', 
    category: 'SAP Data',
    icon: 'Layers',
    description: 'Type I error control methods (Hochberg, Bonferroni, etc.)'
  },
  'x-sap-sensitivity-analyses': { 
    name: 'Sensitivity Analyses', 
    category: 'SAP Data',
    icon: 'FlaskConical',
    description: 'Pre-specified sensitivity and supportive analyses'
  },
  'x-sap-subgroup-analyses': { 
    name: 'Subgroup Analyses', 
    category: 'SAP Data',
    icon: 'GitBranch',
    description: 'Pre-specified subgroup analyses with interaction tests'
  },
  'x-sap-interim-analyses': { 
    name: 'Interim Analyses', 
    category: 'SAP Data',
    icon: 'Clock',
    description: 'Interim analysis plan with stopping boundaries'
  },
  'x-sap-sample-size-calculations': { 
    name: 'Sample Size Calculations', 
    category: 'SAP Data',
    icon: 'Hash',
    description: 'Power and sample size assumptions'
  },
  'x-footnoteConditions': { 
    name: 'Footnote Conditions', 
    category: 'SoA Data',
    icon: 'FileText',
    description: 'Conditional logic from SoA footnotes'
  },
  'x-soaFootnotes': { 
    name: 'SoA Footnotes', 
    category: 'SoA Data',
    icon: 'FileText',
    description: 'Authoritative footnotes from Schedule of Activities'
  },
  'activitySource': { 
    name: 'Activity Source', 
    category: 'SoA Data',
    icon: 'Activity',
    description: 'Whether activity is from SoA or procedure enrichment'
  },
  'x-executionModel-entityMappings': { 
    name: 'Entity Mappings', 
    category: 'Debug/Provenance',
    icon: 'Settings',
    description: 'LLM-resolved entity mappings'
  },
  'x-executionModel-promotionIssues': { 
    name: 'Promotion Issues', 
    category: 'Debug/Provenance',
    icon: 'AlertCircle',
    description: 'Issues during execution model promotion'
  },
  'x-executionModel-integrityIssues': { 
    name: 'Integrity Issues', 
    category: 'Debug/Provenance',
    icon: 'AlertCircle',
    description: 'Data integrity validation results'
  },
  'x-executionModel-classifiedIssues': { 
    name: 'Classified Issues', 
    category: 'Debug/Provenance',
    icon: 'AlertCircle',
    description: 'Categorized extraction issues'
  },
};

const CATEGORY_ICONS: Record<string, typeof Activity> = {
  'Execution Model': Activity,
  'SoA Data': FileText,
  'SAP Data': FileText,
  'Debug/Provenance': Settings,
  'Other': Puzzle,
};

const CATEGORY_COLORS: Record<string, string> = {
  'Execution Model': 'bg-blue-100 text-blue-800 border-blue-200',
  'SoA Data': 'bg-green-100 text-green-800 border-green-200',
  'SAP Data': 'bg-purple-100 text-purple-800 border-purple-200',
  'Debug/Provenance': 'bg-amber-100 text-amber-800 border-amber-200',
  'Other': 'bg-gray-100 text-gray-800 border-gray-200',
};

function getExtensionMeta(url: string) {
  const shortName = url.split('/').pop() || url;
  return EXTENSION_METADATA[shortName] || {
    name: shortName,
    category: 'Other',
    icon: 'Puzzle',
    description: 'Custom extension'
  };
}

function parseExtensionValue(ext: ExtensionAttribute): unknown {
  if (ext.valueString) {
    try {
      return JSON.parse(ext.valueString);
    } catch {
      return ext.valueString;
    }
  }
  return ext.value ?? ext.valueBoolean ?? ext.valueInteger ?? ext.valueCode;
}

// Formatted display components for specific extension types
function VisitWindowsDisplay({ data }: { data: unknown }) {
  if (!Array.isArray(data)) return null;
  const windows = data as { visitName?: string; targetDay?: number; windowBefore?: number; windowAfter?: number; isRequired?: boolean }[];
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b">
            <th className="text-left p-2">Visit</th>
            <th className="text-right p-2">Day</th>
            <th className="text-right p-2">Window</th>
            <th className="text-center p-2">Required</th>
          </tr>
        </thead>
        <tbody>
          {windows.slice(0, 10).map((w, i) => (
            <tr key={i} className="border-b border-muted">
              <td className="p-2">{w.visitName || `Visit ${i + 1}`}</td>
              <td className="text-right p-2">{w.targetDay ?? '-'}</td>
              <td className="text-right p-2">
                {w.windowBefore || w.windowAfter 
                  ? `−${w.windowBefore || 0}/+${w.windowAfter || 0}`
                  : '-'}
              </td>
              <td className="text-center p-2">
                {w.isRequired ? <CheckCircle className="h-3 w-3 text-green-600 mx-auto" /> : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {windows.length > 10 && (
        <p className="text-xs text-muted-foreground mt-2">...and {windows.length - 10} more</p>
      )}
    </div>
  );
}

function DosingRegimensDisplay({ data }: { data: unknown }) {
  if (!Array.isArray(data)) return null;
  const regimens = data as { treatmentName?: string; dose?: string; frequency?: string; route?: string; doseLevels?: { amount: number; unit: string }[] }[];
  
  return (
    <div className="space-y-2">
      {regimens.map((r, i) => (
        <div key={i} className="p-2 bg-muted/50 rounded border">
          <div className="font-medium text-sm">{r.treatmentName || 'Treatment'}</div>
          <div className="flex flex-wrap gap-2 mt-1">
            {r.doseLevels?.map((d, j) => (
              <Badge key={j} variant="secondary" className="text-xs">
                {d.amount} {d.unit}
              </Badge>
            ))}
            {r.dose && <Badge variant="secondary" className="text-xs">{r.dose}</Badge>}
            {r.frequency && <Badge variant="outline" className="text-xs">{r.frequency}</Badge>}
            {r.route && <Badge variant="outline" className="text-xs">{r.route}</Badge>}
          </div>
        </div>
      ))}
    </div>
  );
}

function FootnoteConditionsDisplay({ data }: { data: unknown }) {
  if (!Array.isArray(data)) return null;
  const conditions = data as { text?: string; conditionType?: string; appliesToActivityIds?: string[] }[];
  
  return (
    <div className="space-y-2 max-h-[300px] overflow-auto">
      {conditions.slice(0, 8).map((c, i) => (
        <div key={i} className="p-2 bg-muted/50 rounded border text-xs">
          <div className="flex items-start gap-2">
            {c.conditionType && (
              <Badge variant="outline" className="text-xs shrink-0">{c.conditionType}</Badge>
            )}
            <span className="line-clamp-2">{c.text || 'Condition'}</span>
          </div>
          {c.appliesToActivityIds && c.appliesToActivityIds.length > 0 && (
            <div className="mt-1 text-muted-foreground">
              Applies to {c.appliesToActivityIds.length} activit{c.appliesToActivityIds.length === 1 ? 'y' : 'ies'}
            </div>
          )}
        </div>
      ))}
      {conditions.length > 8 && (
        <p className="text-xs text-muted-foreground">...and {conditions.length - 8} more conditions</p>
      )}
    </div>
  );
}

function StateMachineDisplay({ data }: { data: unknown }) {
  const sm = data as { initialState?: string; terminalStates?: string[]; transitions?: { fromState: string; toState: string }[] };
  if (!sm) return null;
  
  return (
    <div className="space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">Initial:</span>
        <Badge variant="secondary">{sm.initialState || 'Unknown'}</Badge>
      </div>
      {sm.terminalStates && sm.terminalStates.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Terminal:</span>
          {sm.terminalStates.map((s, i) => (
            <Badge key={i} variant="outline">{s}</Badge>
          ))}
        </div>
      )}
      {sm.transitions && (
        <div className="text-muted-foreground">
          {sm.transitions.length} transitions defined
        </div>
      )}
    </div>
  );
}

// Map extension URLs to navigation targets within the app
const EXTENSION_NAV_TARGETS: Record<string, { tab: string; label: string }> = {
  'x-executionModel-stateMachine': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-visitWindows': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-dosingRegimens': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-traversalConstraints': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-timeAnchors': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-repetitions': { tab: 'execution', label: 'View in Execution Model' },
  'x-executionModel-crossoverDesign': { tab: 'execution', label: 'View in Execution Model' },
  'x-footnoteConditions': { tab: 'execution', label: 'View Conditions' },
  'x-soaFootnotes': { tab: 'soa', label: 'View in SoA' },
  'activitySource': { tab: 'soa', label: 'View in SoA' },
};

// Entity type icons and colors
const ENTITY_TYPE_META: Record<string, { icon: typeof Activity; color: string; label: string }> = {
  'StudyDesign': { icon: GitBranch, color: 'bg-purple-100 text-purple-800', label: 'Study Design' },
  'Activity': { icon: Activity, color: 'bg-blue-100 text-blue-800', label: 'Activities' },
  'Encounter': { icon: Calendar, color: 'bg-green-100 text-green-800', label: 'Encounters' },
  'StudyEpoch': { icon: Clock, color: 'bg-amber-100 text-amber-800', label: 'Epochs' },
  'StudyArm': { icon: Users, color: 'bg-pink-100 text-pink-800', label: 'Arms' },
  'ScheduledActivityInstance': { icon: CheckCircle, color: 'bg-cyan-100 text-cyan-800', label: 'Schedule Instances' },
};

// Entities by Type view component
function EntitiesByTypeView({ 
  entities, 
  expandedSections, 
  toggleSection 
}: { 
  entities: { path: string; entity: EntityWithExtensions }[];
  expandedSections: Set<string>;
  toggleSection: (section: string) => void;
}) {
  // Group entities by instanceType
  const groupedByType = useMemo(() => {
    const groups: Record<string, { path: string; entity: EntityWithExtensions }[]> = {};
    
    for (const item of entities) {
      const type = item.entity.instanceType || 'Other';
      if (!groups[type]) {
        groups[type] = [];
      }
      groups[type].push(item);
    }
    
    return groups;
  }, [entities]);

  const typeOrder = ['StudyDesign', 'Activity', 'Encounter', 'StudyEpoch', 'StudyArm', 'ScheduledActivityInstance'];
  const sortedTypes = [
    ...typeOrder.filter(t => groupedByType[t]),
    ...Object.keys(groupedByType).filter(t => !typeOrder.includes(t))
  ];

  if (entities.length === 0) {
    return <p className="text-sm text-muted-foreground">No entities with extensions found.</p>;
  }

  return (
    <div className="space-y-4">
      {sortedTypes.map(type => {
        const items = groupedByType[type];
        if (!items || items.length === 0) return null;
        
        const meta = ENTITY_TYPE_META[type] || { 
          icon: Puzzle, 
          color: 'bg-gray-100 text-gray-800', 
          label: type 
        };
        const TypeIcon = meta.icon;
        const isTypeExpanded = expandedSections.has(`type_${type}`);
        
        return (
          <div key={type} className="border rounded-lg">
            <button
              onClick={() => toggleSection(`type_${type}`)}
              className={cn(
                "w-full flex items-center gap-2 p-3 rounded-t-lg",
                meta.color
              )}
            >
              {isTypeExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              <TypeIcon className="h-4 w-4" />
              <span className="font-medium">{meta.label}</span>
              <Badge variant="outline" className="ml-auto text-xs bg-white/50">
                {items.length} entit{items.length === 1 ? 'y' : 'ies'}
              </Badge>
            </button>
            
            {isTypeExpanded && (
              <div className="p-2 space-y-1 bg-white/50 max-h-[400px] overflow-auto">
                {items.map(({ path, entity }, i) => {
                  const entityName = entity.label || entity.name || entity.id || `${type} ${i + 1}`;
                  const isEntityExpanded = expandedSections.has(path);
                  
                  return (
                    <div key={i} className="border rounded bg-white">
                      <button
                        onClick={() => toggleSection(path)}
                        className="w-full flex items-center gap-2 p-2 hover:bg-muted/30 text-left text-sm"
                      >
                        {isEntityExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        <span className="font-medium truncate flex-1">{entityName}</span>
                        <Badge variant="secondary" className="text-xs">
                          {entity.extensionAttributes?.length} ext
                        </Badge>
                      </button>
                      
                      {isEntityExpanded && (
                        <div className="px-2 pb-2 space-y-1">
                          {entity.extensionAttributes?.map((ext, j) => {
                            const extMeta = getExtensionMeta(ext.url || '');
                            const navTarget = EXTENSION_NAV_TARGETS[ext.url?.split('/').pop() || ''];
                            const parsedValue = parseExtensionValue(ext);
                            
                            return (
                              <div key={j} className="p-2 bg-muted/50 rounded text-xs">
                                <div className="flex items-center justify-between gap-2 mb-1">
                                  <span className="font-medium">{extMeta.name}</span>
                                  {navTarget && (
                                    <Badge 
                                      variant="outline" 
                                      className="text-xs cursor-pointer hover:bg-primary hover:text-primary-foreground"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        // Emit navigation event or use router
                                        const event = new CustomEvent('navigate-tab', { detail: { tab: navTarget.tab } });
                                        window.dispatchEvent(event);
                                      }}
                                    >
                                      {navTarget.label} →
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-muted-foreground mb-2">{extMeta.description}</p>
                                
                                {parsedValue !== undefined && (
                                  <details className="group">
                                    <summary className="cursor-pointer text-blue-600 hover:underline">
                                      View data
                                    </summary>
                                    <pre className="mt-1 p-2 bg-background rounded text-xs font-mono overflow-x-auto max-h-[150px]">
                                      {typeof parsedValue === 'object' 
                                        ? JSON.stringify(parsedValue, null, 2)
                                        : String(parsedValue)
                                      }
                                    </pre>
                                  </details>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Extension card with formatted display
function ExtensionCard({ 
  meta, 
  count, 
  values, 
  expanded, 
  onToggle 
}: { 
  meta: ReturnType<typeof getExtensionMeta>; 
  count: number; 
  values: unknown[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const value = values[0];
  
  // Get formatted display based on extension type
  const getFormattedDisplay = () => {
    switch (meta.name) {
      case 'Visit Windows':
        return <VisitWindowsDisplay data={value} />;
      case 'Dosing Regimens':
        return <DosingRegimensDisplay data={value} />;
      case 'Footnote Conditions':
        return <FootnoteConditionsDisplay data={value} />;
      case 'State Machine':
        return <StateMachineDisplay data={value} />;
      default:
        // Default JSON display
        if (value !== undefined) {
          return (
            <pre className="text-xs font-mono whitespace-pre-wrap overflow-x-auto max-h-[200px] p-2 bg-muted rounded">
              {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
            </pre>
          );
        }
        return null;
    }
  };

  return (
    <div className="border rounded bg-white">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 p-2 hover:bg-muted/30 text-left"
      >
        {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <span className="font-medium text-sm">{meta.name}</span>
        <span className="text-xs text-muted-foreground ml-auto">{meta.description}</span>
        {count > 1 && <Badge variant="secondary" className="text-xs">{count}×</Badge>}
      </button>
      
      {expanded && (
        <div className="p-3 border-t">
          {getFormattedDisplay()}
        </div>
      )}
    </div>
  );
}

export function ExtensionsView({ usdm }: ExtensionsViewProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['studyDesign']));

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Puzzle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Recursively find all entities with extensionAttributes
  const entitiesWithExtensions: { path: string; entity: EntityWithExtensions }[] = [];
  
  const findExtensions = (obj: unknown, path: string) => {
    if (!obj || typeof obj !== 'object') return;
    
    if (Array.isArray(obj)) {
      obj.forEach((item, i) => findExtensions(item, `${path}[${i}]`));
    } else {
      const entity = obj as Record<string, unknown>;
      if (entity.extensionAttributes && Array.isArray(entity.extensionAttributes) && entity.extensionAttributes.length > 0) {
        entitiesWithExtensions.push({
          path,
          entity: entity as EntityWithExtensions,
        });
      }
      Object.entries(entity).forEach(([key, value]) => {
        if (key !== 'extensionAttributes') {
          findExtensions(value, `${path}.${key}`);
        }
      });
    }
  };
  
  findExtensions(usdm, 'root');

  // Group extensions by URL and category
  const extensionsByUrl = useMemo(() => {
    const map = new Map<string, { count: number; values: unknown[]; ext: ExtensionAttribute }>();
    entitiesWithExtensions.forEach(({ entity }) => {
      entity.extensionAttributes?.forEach(ext => {
        const url = ext.url || 'unknown';
        const existing = map.get(url) || { count: 0, values: [], ext };
        existing.count++;
        const parsed = parseExtensionValue(ext);
        if (parsed !== undefined) existing.values.push(parsed);
        map.set(url, existing);
      });
    });
    return map;
  }, [entitiesWithExtensions]);

  // Group by category
  const extensionsByCategory = useMemo(() => {
    const categories: Record<string, { url: string; meta: ReturnType<typeof getExtensionMeta>; count: number; values: unknown[] }[]> = {};
    
    extensionsByUrl.forEach((data, url) => {
      const meta = getExtensionMeta(url);
      if (!categories[meta.category]) {
        categories[meta.category] = [];
      }
      categories[meta.category].push({ url, meta, count: data.count, values: data.values });
    });
    
    return categories;
  }, [extensionsByUrl]);

  // Generate insights
  const insights = useMemo(() => {
    const result: string[] = [];
    
    // Visit windows insight
    const visitWindows = extensionsByUrl.get('https://protocol2usdm.io/extensions/x-executionModel-visitWindows');
    if (visitWindows && visitWindows.values.length > 0) {
      const windows = visitWindows.values[0] as { targetDay?: number }[];
      if (Array.isArray(windows)) {
        const days = windows.map(w => w.targetDay).filter(d => d !== undefined).sort((a, b) => (a || 0) - (b || 0));
        if (days.length > 0) {
          result.push(`${windows.length} visit windows defined (Days ${days[0]} to ${days[days.length - 1]})`);
        }
      }
    }
    
    // Dosing insight
    const dosing = extensionsByUrl.get('https://protocol2usdm.io/extensions/x-executionModel-dosingRegimens');
    if (dosing && dosing.values.length > 0) {
      const regimens = dosing.values[0] as { treatmentName?: string }[];
      if (Array.isArray(regimens)) {
        const treatments = [...new Set(regimens.map(r => r.treatmentName).filter(Boolean))];
        result.push(`${regimens.length} dosing regimen${regimens.length !== 1 ? 's' : ''} for ${treatments.join(', ') || 'study treatments'}`);
      }
    }
    
    // Footnotes insight
    const footnotes = extensionsByUrl.get('https://protocol2usdm.io/extensions/x-footnoteConditions');
    if (footnotes && footnotes.values.length > 0) {
      const conditions = footnotes.values[0] as unknown[];
      if (Array.isArray(conditions)) {
        result.push(`${conditions.length} footnote condition${conditions.length !== 1 ? 's' : ''} linked to activities`);
      }
    }
    
    // State machine insight
    const stateMachine = extensionsByUrl.get('https://protocol2usdm.io/extensions/x-executionModel-stateMachine');
    if (stateMachine && stateMachine.values.length > 0) {
      const sm = stateMachine.values[0] as { transitions?: unknown[] };
      if (sm?.transitions) {
        result.push(`State machine with ${sm.transitions.length} transitions defined`);
      }
    }
    
    return result;
  }, [extensionsByUrl]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  if (entitiesWithExtensions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Puzzle className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM extensions found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Extensions allow custom data to be added to USDM entities
          </p>
        </CardContent>
      </Card>
    );
  }

  const categoryOrder = ['Execution Model', 'SoA Data', 'Debug/Provenance', 'Other'];

  return (
    <div className="space-y-6">
      {/* Summary with Insights */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Puzzle className="h-5 w-5" />
            USDM Extensions Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{entitiesWithExtensions.length}</div>
              <div className="text-xs text-muted-foreground">Entities with Extensions</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{extensionsByUrl.size}</div>
              <div className="text-xs text-muted-foreground">Extension Types</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">
                {Array.from(extensionsByUrl.values()).reduce((sum, e) => sum + e.count, 0)}
              </div>
              <div className="text-xs text-muted-foreground">Total Extensions</div>
            </div>
            <div className="p-3 bg-muted rounded-lg">
              <div className="text-2xl font-bold">{Object.keys(extensionsByCategory).length}</div>
              <div className="text-xs text-muted-foreground">Categories</div>
            </div>
          </div>

          {/* Insights */}
          {insights.length > 0 && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-medium text-sm text-blue-800 mb-2 flex items-center gap-2">
                <CheckCircle className="h-4 w-4" />
                Key Insights
              </h4>
              <ul className="space-y-1">
                {insights.map((insight, i) => (
                  <li key={i} className="text-sm text-blue-700">• {insight}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Extensions by Category */}
          <div className="space-y-4">
            {categoryOrder.map(category => {
              const extensions = extensionsByCategory[category];
              if (!extensions || extensions.length === 0) return null;
              
              const CategoryIcon = CATEGORY_ICONS[category] || Puzzle;
              const categoryColor = CATEGORY_COLORS[category] || CATEGORY_COLORS['Other'];
              
              return (
                <div key={category} className={cn("border rounded-lg", categoryColor.split(' ')[2])}>
                  <button
                    onClick={() => toggleSection(category)}
                    className={cn(
                      "w-full flex items-center gap-2 p-3 rounded-t-lg",
                      categoryColor.split(' ').slice(0, 2).join(' ')
                    )}
                  >
                    {expandedSections.has(category) ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                    <CategoryIcon className="h-4 w-4" />
                    <span className="font-medium">{category}</span>
                    <Badge variant="outline" className="ml-auto text-xs">
                      {extensions.length} type{extensions.length !== 1 ? 's' : ''}
                    </Badge>
                  </button>
                  
                  {expandedSections.has(category) && (
                    <div className="p-3 space-y-2 bg-white/50">
                      {extensions.map(({ url, meta, count, values }) => (
                        <ExtensionCard 
                          key={url} 
                          meta={meta} 
                          count={count} 
                          values={values}
                          expanded={expandedSections.has(url)}
                          onToggle={() => toggleSection(url)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Extensions by Entity - Grouped by Type */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Code className="h-5 w-5" />
            Extensions by Entity
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Entities with custom extension attributes, grouped by type
          </p>
        </CardHeader>
        <CardContent>
          <EntitiesByTypeView 
            entities={entitiesWithExtensions}
            expandedSections={expandedSections}
            toggleSection={toggleSection}
          />
        </CardContent>
      </Card>
    </div>
  );
}

export default ExtensionsView;
