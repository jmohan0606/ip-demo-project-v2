/** Request to open the evidence modal for one driver of one transition. */
export interface EvidenceRequest {
  driverId: string;
  versionId: string;
  transitionLabel: string;
  driverIndex: number;
  driverCount: number;
}
