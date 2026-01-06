'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Stethoscope, 
  Cpu,
  AlertTriangle,
} from 'lucide-react';

interface ProceduresDevicesViewProps {
  usdm: Record<string, unknown> | null;
}

interface Code {
  code: string;
  decode?: string;
  codeSystem?: string;
}

interface Procedure {
  id: string;
  name?: string;
  description?: string;
  procedureType?: Code | string;
  code?: Code;
  instanceType?: string;
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
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="font-medium">
                      {procedure.name || `Procedure ${i + 1}`}
                    </div>
                    {procedure.procedureType && (
                      <Badge variant="outline">
                        {typeof procedure.procedureType === 'string' 
                          ? procedure.procedureType 
                          : procedure.procedureType.decode || procedure.procedureType.code}
                      </Badge>
                    )}
                  </div>
                  {procedure.description && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {procedure.description}
                    </p>
                  )}
                  {procedure.code && (
                    <Badge variant="secondary" className="mt-2 text-xs">
                      {procedure.code.code}: {procedure.code.decode || 'N/A'}
                    </Badge>
                  )}
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
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="font-medium">
                      {device.name || `Device ${i + 1}`}
                    </div>
                    {device.deviceIdentifier && (
                      <Badge variant="outline">{device.deviceIdentifier}</Badge>
                    )}
                  </div>
                  {device.description && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {device.description}
                    </p>
                  )}
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

      {/* Safety Note */}
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="py-4">
          <div className="flex items-center gap-2 text-amber-800">
            <AlertTriangle className="h-5 w-5" />
            <span className="text-sm">
              Review all procedures and devices against protocol source documents
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ProceduresDevicesView;
