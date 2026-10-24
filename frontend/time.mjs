export function shanghaiInput(value){if(!value)return '';const n=Date.parse(value);if(!Number.isFinite(n))return '';return new Date(n+8*3600000).toISOString().replace(/Z$/,'').replace(/\.000$/,'');}
export function fromShanghaiInput(value){return value?(value.length===16?value+':00':value)+'+08:00':'';}
