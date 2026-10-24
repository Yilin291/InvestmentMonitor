const fs=require('fs');
function assess(e){
 const by=Object.fromEntries(e.cases.map(c=>[c.name,c]));const checks=[];
 const add=(name,passed)=>checks.push({name,passed:!!passed});
 add('no_credentials_denied',by.no_gateway?.status===401);
 add('wrong_business_secret_denied',by.wrong_business_secret?.status===401);
 add('correct_business_secret_accepted',by.secret_presence?.status===200);
 const present=by.secret_presence?.body?.secrets_present||{};
 add('required_secrets_present',['APP_ORIGIN','DEMO_PASSWORD','SESSION_SECRET','TICK_SECRET','FUYAO_API_KEY','DEEPSEEK_API_KEY','SUPABASE_SERVICE_ROLE_KEY','WATCHLIST_DATA_ORIGIN'].every(k=>present[k]===true));
 add('owner_spoof_denied',by.owner_spoof?.status===403);
 add('anonymous_rpc_denied',[401,403].includes(by.anonymous_direct_rpc?.status)&&by.anonymous_direct_rpc.body.code==='42501');
 for(const name of ['commit','independent_readback','recovery_write','recovery_readback'])add(name,by[name]?.status===200&&by[name]?.body?.result?.found===true&&by[name]?.body?.transport==='https');
 add('commit_id_matches_readback',by.commit?.body?.result?.id===by.independent_readback?.body?.result?.id&&!!by.commit?.body?.result?.id);
 add('recovery_id_matches_readback',by.recovery_write?.body?.result?.id===by.recovery_readback?.body?.result?.id&&!!by.recovery_write?.body?.result?.id);
 add('unique_violation',by.unique_conflict?.status===409&&by.unique_conflict?.body?.sqlstate==='23505');
 add('intentional_transaction_failure',by.intentional_rollback?.status===400&&by.intentional_rollback?.body?.sqlstate==='P0001');
 for(const name of ['rollback_readback','cleanup_commit','cleanup_recovery'])add(name,by[name]?.status===200&&by[name]?.body?.result?.found===false);
 return {checks,functional_passed:checks.every(c=>c.passed),platform_gateway_jwt_enforced:by.no_gateway_valid_business_secret?.status===200?false:null,feasibility_gate_passed:false,remaining_gates:['platform_execution_limit_basis','lead_public_api_prefix_review','same_origin_cookie_readback'],not_product_acceptance:true};
}
module.exports={assess};
if(require.main===module){const result=assess(JSON.parse(fs.readFileSync(process.argv[2])));const dest=process.argv[3];if(dest){if(fs.existsSync(dest))throw Error('evidence_exists');fs.writeFileSync(dest,JSON.stringify(result,null,2));}console.log(JSON.stringify(result));process.exitCode=result.functional_passed?0:1;}
