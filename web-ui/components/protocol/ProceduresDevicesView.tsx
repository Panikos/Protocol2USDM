'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField, CodeLink } from '@/components/semantic';
import { EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic/EditableCodedValue';
import { designPath, versionPath } from '@/lib/semantic/schema';
import { 
  Stethoscope, 
  Cpu,
} from 'lucide-react';

interface ProceduresDevicesViewProps {
  usdm: Record<string, unknown> | null;
}

interface Code {
  code: string;
  decode?: string;
  codeSystem?: string;
  url?: string;
}

interface ExtensionAttribute {
  url: string;
  value?: unknown;
  valueString?: string;
  valueBoolean?: boolean;
}

interface Procedure {
  id: string;
  name?: string;
  description?: string;
  procedureType?: Code | string;
  code?: Code;
  extensionAttributes?: ExtensionAttribute[];
  instanceType?: string;
}

/** Extract multi-system codes from x-procedureCodes extension. */
function getProcedureCodes(proc: Procedure): Code[] {
  const ext = proc.extensionAttributes?.find(
    (e) => e.url?.endsWith('x-procedureCodes'),
  );
  if (!ext || !Array.isArray(ext.value)) return [];
  return ext.value as Code[];
}

interface Device {
  id: string;
  name?: string;
  description?: string;
  deviceIdentifier?: string;
  manufacturer?: string;
  instanceType?: string;
}

export function ProceduresDevicesView({ usdm }: ProceduresDevicesViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Stethoscope className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract data from USDM structure
  // Per USDM spec: Procedures are nested within Activities via definedProcedures
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Collect procedures from multiple locations (with deduplication):
  // 1. studyDesign.procedures (direct array)
  // 2. activities' definedProcedures (nested)
  const procedureMap = new Map<string, Procedure>();
  
  // Helper to add procedure with deduplication by ID or name
  const addProcedure = (proc: Procedure) => {
    const key = proc.id || proc.name || JSON.stringify(proc);
    if (!procedureMap.has(key)) {
      procedureMap.set(key, proc);
    }
  };
  
  // Check studyDesign.procedures first
  const directProcedures = (studyDesign.procedures as Procedure[]) ?? [];
  directProcedures.forEach(addProcedure);
  
  // Also check activities' definedProcedures (nested format)
  const activities = (studyDesign.activities as { definedProcedures?: Procedure[] }[]) ?? [];
  for (const activity of activities) {
    if (activity.definedProcedures) {
      activity.definedProcedures.forEach(addProcedure);
    }
  }
  
  const procedures = Array.from(procedureMap.values());

  // USDM-compliant: medicalDevices are at studyVersion level (per dataStructure.yml)
  const devices = (version?.medicalDevices as Device[]) ?? 
                  (studyDesign.medicalDevices as Device[]) ?? [];

  const hasData = procedures.length > 0 || devices.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Stethoscope className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No procedures or devices found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Medical procedures and device information will appear here when available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{procedures.length}</div>
                <div className="text-xs text-muted-foreground">Procedures</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{devices.length}</div>
                <div className="text-xs text-muted-foreground">Devices</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Procedures */}
      {procedures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5" />
              Procedures
              <Badge variant="secondary">{procedures.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {procedures.map((procedure, i) => (
                <div key={procedure.id || i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <EditableField
                      path={designPath('procedures', procedure.id, 'name')}
                      value={procedure.name || `Procedure ${i + 1}`}
                      label=""
                      className="font-medium"
                      placeholder="Procedure name"
                    />
                    <EditableCodedValue
                      path={designPath('procedures', procedure.id, 'procedureType')}
                      value={typeof procedure.procedureType === 'string' ? { decode: procedure.procedureType } : procedure.procedureType}
                      options={CDISC_TERMINOLOGIES.procedureType ?? []}
                      showCode
                      placeholder="Type"
                    />
                  </div>
                  <EditableField
                    path={designPath('procedures', procedure.id, 'description')}
                    value={procedure.description || ''}
                    label=""
                    type="textarea"
                    className="text-sm text-muted-foreground mt-1"
                    placeholder="No description"
                  />
                  {(() => {
                    const allCodes = getProcedureCodes(procedure);
                    if (allCodes.length > 0) {
                      return (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {allCodes.map((c, ci) => (
                            <CodeLink
                              key={`${c.codeSystem}-${c.code}-${ci}`}
                              code={c.code}
                              decode={c.code}
                              codeSystem={c.codeSystem}
                              codeOnly
                              variant="secondary"
                              className="text-xs"
                            />
                          ))}
                        </div>
                      );
                    }
                    if (procedure.code) {
                      return (
                        <CodeLink code={procedure.code.code} decode={`${procedure.code.code}: ${procedure.code.decode || 'N/A'}`} codeSystem={procedure.code.codeSystem} variant="secondary" className="mt-2 text-xs" />
                      );
                    }
                    return null;
                  })()}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Devices */}
      {devices.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-5 w-5" />
              Medical Devices
              <Badge variant="secondary">{devices.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {devices.map((device, i) => (
                <div key={device.id || i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <EditableField
                      path={versionPath('medicalDevices', device.id, 'name')}
                      value={device.name || `Device ${i + 1}`}
                      label=""
                      className="font-medium"
                      placeholder="Device name"
                    />
                    {device.deviceIdentifier && (
                      <Badge variant="outline">{device.deviceIdentifier}</Badge>
                    )}
                  </div>
                  <EditableField
                    path={versionPath('medicalDevices', device.id, 'description')}
                    value={device.description || ''}
                    label=""
                    type="textarea"
                    className="text-sm text-muted-foreground mt-1"
                    placeholder="No description"
                  />
                  {device.manufacturer && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Manufacturer: {device.manufacturer}
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

export default ProceduresDevicesView;
