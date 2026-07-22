/** Request to open the evidence modal for one transition (T2-2). The modal
 * loads the transition's FULL ordered driver set and pages through it;
 * initialDriverId selects where to open (omitted = the top-ranked driver). */
export interface EvidenceRequest {
  versionId: string;
  fromMonthId: string;
  toMonthId: string;
  transitionLabel: string;
  initialDriverId?: string;
}
