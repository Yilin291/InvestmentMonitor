// SSE scheduled closures, verified against the two official notices on 2026-10-24.
// Does not claim coverage of emergency suspensions or security-specific trading halts.
export const SSE_CALENDAR={
 version:'sse-2026-notice45-notice22-v1',exchange:'SH',year:2026,verified_at:'2026-10-24',
 sources:['https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml','https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml'],
 closures:[['2026-01-01','2026-01-03'],['2026-02-15','2026-02-23'],['2026-04-04','2026-04-06'],['2026-05-01','2026-05-05'],['2026-06-19','2026-06-21'],['2026-09-25','2026-09-27'],['2026-10-01','2026-10-07']]
};
export const SZSE_CALENDAR={
 version:'szse-2026-notice481-v1',exchange:'SZ',year:2026,verified_at:'2026-10-24',
 sources:['https://www.szse.cn/disclosure/notice/general/t20251222_618087.html','https://dataclouds.cninfo.com.cn/sjother2/regulatory/2025/20251222/50b258f0d89b4076b459eb746a7e100d.pdf'],
 closures:[['2026-01-01','2026-01-03'],['2026-02-15','2026-02-23'],['2026-04-04','2026-04-06'],['2026-05-01','2026-05-05'],['2026-06-19','2026-06-21'],['2026-09-25','2026-09-27'],['2026-10-01','2026-10-07']]
};
export function exchangeCalendar(market='SH'){const calendar={SH:SSE_CALENDAR,SZ:SZSE_CALENDAR}[market];if(!calendar)throw Error('instrument_scope_unsupported');return calendar;}
export function scheduledClosed(date,market='SH'){const calendar=exchangeCalendar(market),weekday=new Date(date+'T12:00:00+08:00').getUTCDay();return [0,6].includes(weekday)||calendar.closures.some(([a,b])=>date>=a&&date<=b);}
