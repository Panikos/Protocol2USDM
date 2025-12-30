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

interface Procedure {
  id: string;
  name?: string;
  description?: string;
  procedureType?: string;
  code?: { code: string; decode?: string };
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
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Get procedures
  const procedures = (studyDesign.procedures as Procedure[]) ?? 
    (version?.procedures as Procedure[]) ?? [];

  // Get devices
  const devices = (studyDesign.studyDevices as Device[]) ?? 
    (version?.studyDevices as Device[]) ?? [];

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
                      <Badge variant="outline">{procedure.procedureType}</Badge>
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
