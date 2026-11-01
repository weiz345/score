const path=require('path');
const fs = require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(path.join(__dirname,'..','templates/dataset.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function element(){return {children:[],value:'',checked:false,hidden:false,append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=[...xs]},closest(){return this.parent||(this.parent=element())}}}
async function check(dataset,file){
 const data=JSON.parse(fs.readFileSync(file,'utf8')),els={};const get=id=>els[id]||(els[id]=element());
 get('k').value='200';get('category').value='all';get('gender').value='all';get('sort').value='desc';const heading=element();
 const context={URLSearchParams,location:{search:'?set='+dataset},document:{getElementById:get,createElement:element,createTextNode:text=>({textContent:text}),querySelector:()=>heading},fetch:async()=>({ok:true,json:async()=>data}),Number,Set,Error};
 vm.runInNewContext(script,context);await new Promise(resolve=>setImmediate(resolve));assert(!get('error').textContent,get('error').textContent);assert.equal(get('gallery').children.length,data.pictures.length);
 if(data.unranked){assert(get('order-control').hidden);assert(heading.textContent.includes('unranked'));assert(!data.pictures.some(p=>'score'in p||'rank'in p));get('gender').value='Women';get('gender').onchange();assert.equal(get('gallery').children.length,data.pictures.filter(p=>p.gender==='Women').length);get('gender').value='Men';get('gender').onchange();assert.equal(get('gallery').children.length,data.pictures.filter(p=>p.gender==='Men').length)}
 console.log('PASS rendering',dataset);
}
(async()=>{await check('small-creators',path.join(__dirname,'..','data/small-creators/rankings.json'));await check('creator-service',path.join(__dirname,'..','data/creator-service/rankings.json'))})().catch(e=>{console.error(e);process.exit(1)});
