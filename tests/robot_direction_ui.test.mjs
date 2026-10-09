import test from "node:test";
import assert from "node:assert/strict";
import { POSITIONS, directionSignals, directionSummary, newJournal, validateJournal, claimPosition, finishPosition } from "../tools/robot_direction_ui.mjs";
const face = { count: 1, robotHeading: 0 };
test("robot-left-positive positions match the raw axis, not observer left/right", () => {
  assert.deepEqual(POSITIONS.map(p=>p.expected_axis_deg), [90,30,150]);
  assert.deepEqual(POSITIONS.map(p=>p.heading_left_positive_deg), [0,60,-60]);
  for (const p of POSITIONS) {
    const s = directionSignals(p, face, {valid:true, speech_detected:true, axis_deg:p.expected_axis_deg}, 50);
    assert.equal(s.expectedError, 0);
    assert.equal(s.bearing, p.heading_left_positive_deg);
    assert.equal(s.separation, Math.abs(p.heading_left_positive_deg));
  }
});
test("missing speech, stale or invalid angles are retained but never interpreted as direction", () => {
  for (const [doa, age] of [[null, 10], [{valid:true,axis_deg:116,speech_detected:false},20],
      [{valid:true,axis_deg:116,speech_detected:true},700], [{valid:true,axis_deg:181,speech_detected:true},20],
      [{valid:true,axis_deg:116,speech_detected:true},-1]]) {
    const s=directionSignals(POSITIONS[0],face,doa,age);
    assert.equal(s.usable,false); assert.equal(s.expectedError,null); assert.equal(s.bearing,null);
    assert.ok(s.codes.length);
  }
});
test("unexpected direction is a number, not a placement accusation or start gate", () => {
  const s=directionSignals(POSITIONS[2],face,{valid:true,axis_deg:116,speech_detected:true},20);
  assert.equal(s.expectedError,-34); assert.equal(s.bearing,-26); assert.deepEqual(s.codes,[]);
  const noFace=directionSignals(POSITIONS[0],null,{valid:true,axis_deg:90,speech_detected:true},20,650,false);
  assert.equal(noFace.usable,true); assert.equal(noFace.separation,null);
});
test("summary excludes inactive speech and has no calibration/pass decision", () => {
  const rows=[90,100,110].map(x=>({direction_usable:true,direction_doa_fresh:true,doa_axis_deg:x,expected_axis_error_deg:x-90}));
  rows.push({direction_usable:false,doa_axis_deg:0});
  const s=directionSummary(rows);
  assert.equal(s.speech_direction_rows,3); assert.equal(s.median_raw_axis_deg,100);
  assert.equal(s.raw_axis_median_absolute_deviation_deg,10);
  assert.equal(directionSummary([]).median_raw_axis_deg,null);
  assert.equal("passed" in s,false);
});
test("journal enforces front-left-right, one start each, fixed distance, partial stop", () => {
  let j=newJournal("session");
  assert.throws(()=>claimPosition(j,1,"id",100));
  assert.throws(()=>claimPosition(j,0,"id",0));
  for (let i=0;i<3;i++) {
    j=claimPosition(j,i,"id"+i,100);
    assert.throws(()=>claimPosition(j,i,"again",100));
    j=finishPosition(j,{position_id:POSITIONS[i].id,csv:"x",base:"x",metadata:JSON.stringify({diagnostic_id:"id"+i})},true);
    assert.throws(()=>claimPosition(j,i,"repeat",100));
  }
  assert.throws(()=>claimPosition(j,3,"fourth",100));
  let stopped=claimPosition(newJournal("partial"),0,"partial",100);
  stopped=finishPosition(stopped,{position_id:"front",csv:"x",base:"x",metadata:'{"diagnostic_id":"partial"}'},false);
  assert.throws(()=>claimPosition(stopped,1,"second",100));
  assert.throws(()=>validateJournal({schema:"wrong"}));
  let next=claimPosition(newJournal("fixed"),0,"first",100);
  next=finishPosition(next,{position_id:"front",csv:"x",base:"x",metadata:'{"diagnostic_id":"first"}'},true);
  assert.throws(()=>claimPosition(next,1,"second",150));
  assert.throws(()=>finishPosition(claimPosition(next,1,"second",100),{position_id:"right60",metadata:'{"diagnostic_id":"second"}'},true));
});
