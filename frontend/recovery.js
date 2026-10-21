/* Pure retry policy, also exercised by the Node regression test. */
(function(root){
 const policy={maxFailures:6,delay:n=>Math.min(2000*2**Math.max(0,n-1),30000),
  permanent:error=>Number.isInteger(error?.status)&&error.status>=400&&error.status<500&&![408,429].includes(error.status)};
 if(typeof module!=='undefined')module.exports=policy;else root.RegDataRecovery=policy;
})(typeof window!=='undefined'?window:this);
