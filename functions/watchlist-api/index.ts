import {handler} from './core.js';
Deno.serve(handler((name: string) => Deno.env.get(name)));
