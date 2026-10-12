"use client";
import {useEffect, useRef, useState} from "react";
import {Icon} from "@/components/Icon";
import {PreviewPage, responseError} from "@/lib/api";

export type EditItem = {type:string;page:number;unit:"normalized";x?:number;y?:number;width?:number;height?:number;text?:string;fontSize?:number;color?:string;fill?:string;lineWidth?:number;points?:number[][];name?:string;value?:string};
type FormField = {page:number;name:string;type:string;value:string;readonly:boolean;checked?:boolean;choices?:string[]};
type Props = {locale:string;file:File;pages:PreviewPage[];forms:boolean;items:EditItem[];onItems:(items:EditItem[])=>void;values:Record<string,string|boolean>;onValues:(values:Record<string,string|boolean>)=>void;image?:File;onImage:(file:File)=>void};

export function DocumentEditor({locale,file,pages,forms,items,onItems,values,onValues,image,onImage}:Props) {
  const t=(ru:string,en:string)=>locale==="ru"?ru:en;
  const [pageIndex,setPageIndex]=useState(0);
  const [mode,setMode]=useState(forms?"text":"text");
  const [text,setText]=useState("");
  const [color,setColor]=useState("#292638");
  const [size,setSize]=useState(18);
  const [fill,setFill]=useState(false);
  const [draft,setDraft]=useState<EditItem|null>(null);
  const [fields,setFields]=useState<FormField[]>([]);
  const [formError,setFormError]=useState("");
  const [inspecting,setInspecting]=useState(false);
  const [imageUrl,setImageUrl]=useState("");
  const start=useRef<number[]|null>(null);
  const current=pages[Math.min(pageIndex,pages.length-1)];
  const pageNum=(current?.page??0)+1;
  const width=current?.width||595;
  const height=current?.height||842;
  useEffect(()=>{if(!image){setImageUrl("");return;}const url=URL.createObjectURL(image);setImageUrl(url);return()=>URL.revokeObjectURL(url);},[image]);
  useEffect(()=>{
    if(!forms)return;
    const controller=new AbortController();
    setInspecting(true);setFormError("");
    const fd=new FormData();fd.append("file",file);
    fetch("/api/pdf-forms/inspect",{method:"POST",body:fd,signal:controller.signal}).then(async response=>{if(!response.ok)throw await responseError(response);return response.json();}).then(data=>{setFields(data.fields||[]);}).catch(error=>{if(!controller.signal.aborted)setFormError(error.message);}).finally(()=>{if(!controller.signal.aborted)setInspecting(false);});
    return()=>controller.abort();
  },[file,forms]);
  const point=(e:React.PointerEvent<SVGSVGElement>)=>{const rect=e.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height))];};
  const make=(p:number[]):EditItem=>({type:mode,page:pageNum,unit:"normalized",x:p[0],y:p[1],color,fontSize:size,lineWidth:2,...(forms?{name:text.trim()||`field_${items.length+1}`}:{text}),...(mode==="rectangle"&&fill?{fill:color}:{})});
  const renderItem=(item:EditItem,i:number)=>{
    const x=(item.x||0)*width,y=(item.y||0)*height,w=(item.width||0)*width,h=(item.height||0)*height;
    if(forms)return <g key={i}><rect x={x} y={y} width={w} height={h} fill="#7055e820" stroke="#7055e8" strokeDasharray="5 3"/><text x={x+4} y={y+14} fontSize={11} fill="#7055e8">{item.name}</text>{item.type==="checkbox"&&<path d={`M ${x+4} ${y+h/2} l ${w/4} ${h/4} l ${w/2} ${-h/2}`} fill="none" stroke="#7055e8"/>}</g>;
    if(item.type==="text")return <text key={i} x={x} y={y} fontSize={item.fontSize} fill={item.color} fontFamily="Arial, sans-serif">{item.text}</text>;
    if(item.type==="freehand")return <polyline key={i} points={item.points?.map(p=>`${p[0]*width},${p[1]*height}`).join(" ")} stroke={item.color} strokeWidth={item.lineWidth} strokeLinecap="round" strokeLinejoin="round" fill="none"/>;
    if(item.type==="image")return <image key={i} href={imageUrl} x={x} y={y} width={w} height={h} preserveAspectRatio="xMidYMid meet"/>;
    return <rect key={i} x={x} y={y} width={w} height={h} fill={item.fill||"none"} stroke={item.color} strokeWidth={item.lineWidth}/>;
  };
  return <div className="document-editor">
    {forms&&<div className="form-fields"><h3>{t("Поля документа","Document fields")}</h3>{inspecting&&<p role="status">{t("Читаем поля…","Reading fields…")}</p>}{formError&&<p role="alert" className="workspace-error">{formError}</p>}{!inspecting&&!formError&&fields.length===0&&<p className="option-note">{t("В документе пока нет полей. Добавьте их на странице ниже.","No form fields yet. Add fields to the page below.")}</p>}{fields.map(field=><label key={`${field.page}-${field.name}`} className={field.type==="CheckBox"?"check-field":"field"}><span>{field.name} <small>· {t("стр.","p.")} {field.page}</small></span>{field.type==="CheckBox"?<input type="checkbox" disabled={field.readonly} checked={Boolean(values[field.name]??field.checked)} onChange={e=>onValues({...values,[field.name]:e.target.checked})}/>:field.choices?.length?<select disabled={field.readonly} value={String(values[field.name]??field.value??"")} onChange={e=>onValues({...values,[field.name]:e.target.value})}>{field.choices.map(choice=><option key={choice}>{choice}</option>)}</select>:<input disabled={field.readonly} value={String(values[field.name]??field.value??"")} onChange={e=>onValues({...values,[field.name]:e.target.value})}/>}</label>)}</div>}
    <div className="editor-toolbar" role="toolbar" aria-label={t("Инструменты редактора","Editor tools")}>{(forms?[["text",t("Текстовое поле","Text field"),"text"],["checkbox",t("Флажок","Checkbox"),"check"]]:[["text",t("Текст","Text"),"text"],["image",t("Изображение","Image"),"image"],["rectangle",t("Фигура","Shape"),"crop"],["freehand",t("Рисовать","Draw"),"pen"]]).map(([key,label,icon])=><button type="button" key={key} className={mode===key?"editor-tool active":"editor-tool"} aria-pressed={mode===key} onClick={()=>setMode(key)}><Icon name={icon} size={17}/>{label}</button>)}<button type="button" className="icon-button" disabled={!items.length} onClick={()=>onItems(items.slice(0,-1))} aria-label={t("Отменить последнее","Undo last change")} title={t("Отменить последнее","Undo last change")}><Icon name="undo" size={18}/></button></div>
    <div className="editor-settings">{(forms||mode==="text")&&<label className="field"><span>{forms?t("Название поля","Field name"):t("Добавить текст","Text to add")}</span><input value={text} onChange={e=>setText(e.target.value)} placeholder={forms?t("Например: Имя","Example: Name"):t("Введите текст…","Enter text…")}/></label>}{!forms&&mode!=="image"&&<><label className="field"><span>{t("Цвет","Color")}</span><input type="color" value={color} onChange={e=>setColor(e.target.value)}/></label>{mode==="text"&&<label className="field"><span>{t("Размер","Size")}</span><input type="number" min={6} max={144} value={size} onChange={e=>setSize(Math.max(6,Math.min(144,Number(e.target.value))))}/></label>}{mode==="rectangle"&&<label className="check-field"><input type="checkbox" checked={fill} onChange={e=>setFill(e.target.checked)}/>{t("Заливка","Fill")}</label>}</>}{!forms&&mode==="image"&&<label className="field"><span>{t("Изображение","Image")}</span><input type="file" accept="image/png,image/jpeg" onChange={e=>e.target.files?.[0]&&onImage(e.target.files[0])}/><small>{t("Одно изображение для всех вставок в этом документе.","One image is used for all image placements in this document.")}</small></label>}</div>
    <p className="editor-hint">{forms?t("Протяните рамку на странице, чтобы создать поле.","Drag a rectangle on the page to create a field."):mode==="text"?t("Введите текст и нажмите на странице, чтобы разместить его.","Enter text, then click the page to place it."):mode==="freehand"?t("Рисуйте прямо на странице мышью или пальцем.","Draw on the page with your mouse or finger."):t("Протяните рамку на странице, чтобы задать размер и положение.","Drag a rectangle on the page to set size and position.")}</p>
    <div className="editor-pagination"><button type="button" className="icon-button" disabled={pageIndex===0} onClick={()=>setPageIndex(i=>i-1)} aria-label={t("Предыдущая страница","Previous page")}><Icon name="chevron-left" size={18}/></button><label>{t("Страница","Page")} <select value={pageIndex} onChange={e=>setPageIndex(Number(e.target.value))}>{pages.map((page,i)=><option key={page.page} value={i}>{page.page+1}</option>)}</select> / {pages.length}</label><button type="button" className="icon-button" disabled={pageIndex>=pages.length-1} onClick={()=>setPageIndex(i=>i+1)} aria-label={t("Следующая страница","Next page")}><Icon name="chevron-right" size={18}/></button></div>
    {current&&<div className="editor-canvas" style={{aspectRatio:`${width}/${height}`}}>{current.thumb&&<img src={current.thumb} alt={t("Страница PDF","PDF page")} draggable={false}/>}<svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={t("Область редактирования PDF","PDF editing area")} onPointerDown={e=>{if(!forms&&mode==="text"&&!text.trim())return;if(mode==="image"&&!image)return;const p=point(e);e.currentTarget.setPointerCapture(e.pointerId);if(!forms&&mode==="text"){onItems([...items,make(p)]);return;}start.current=p;setDraft({...make(p),...(mode==="freehand"?{points:[p]}:{width:0,height:0})});}} onPointerMove={e=>{if(!start.current)return;const p=point(e),s=start.current;setDraft(previous=>previous?mode==="freehand"?{...previous,points:[...(previous.points||[]),p]}:{...previous,x:Math.min(p[0],s[0]),y:Math.min(p[1],s[1]),width:Math.abs(p[0]-s[0]),height:Math.abs(p[1]-s[1])}:null);}} onPointerUp={()=>{if(draft&&((draft.points?.length||0)>1||((draft.width||0)>.005&&(draft.height||0)>.005)))onItems([...items,draft]);start.current=null;setDraft(null);}} onPointerCancel={()=>{start.current=null;setDraft(null);}}>{items.filter(item=>item.page===pageNum).map(renderItem)}{draft&&renderItem(draft,-1)}</svg></div>}
    {items.length>0&&<div className="edit-list"><h3>{t("Добавленные элементы","Added items")} · {items.length}</h3>{items.map((item,i)=><div key={i}><span>{i+1}. {item.name||item.text||({rectangle:t("Фигура","Shape"),freehand:t("Рисунок","Drawing"),image:t("Изображение","Image")}[item.type]||item.type)} <small>· {t("стр.","p.")} {item.page}</small></span><button className="icon-button" type="button" onClick={()=>onItems(items.filter((_,index)=>index!==i))} aria-label={t("Удалить элемент","Remove item")}><Icon name="close" size={15}/></button></div>)}</div>}
  </div>;
}

