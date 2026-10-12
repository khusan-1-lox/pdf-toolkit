"use client";

import {useEffect,useRef,useState} from "react";
import Link from "next/link";
import {DropZone,getAcceptForSlug} from "@/components/DropZone";
import {Icon} from "@/components/Icon";
import {getTool} from "@/lib/tools";
import {callTool,callCompare,Comparison,previewPdf,PreviewPage} from "@/lib/api";
import {defaultOptions,Options,ToolOptions} from "@/components/ToolOptions";
import {DocumentEditor,EditItem} from "@/components/DocumentEditor";
import {PageOverlay} from "./PageOverlay";
import "./workspace.css";

type PageItem=PreviewPage&{id:string;file:File;rotation:number};
type WorkflowStep={id:number;slug:string;options:Options};
const workflowTools=["compress","rotate","page-numbers","watermark","crop","protect"];
const inputKeys:Record<string,string[]>={
  split:["pages"],delete:["pages"],"extract-pages":["pages"],compress:["quality"],rotate:["angle"],
  watermark:["text","image","position","opacity","fontSize","color","rotation"],
  "page-numbers":["position","format","fontSize","color","margin","startNumber"],
  crop:["mode","pages","unit","top","bottom","left","right","x","y","w","h"],
  protect:["user_password","owner_password","allow_print","allow_copy","allow_modify","allow_annotate"],
  unlock:["password"],redact:["texts","hide_images"],sign:["image","position","opacity","page"],
  "pdf-to-jpg":["dpi"],"jpg-to-pdf":["orientation","pageSize","margin"],"scan-to-pdf":["orientation","pageSize","margin"],
  "ocr-pdf":["lang"],"html-to-pdf":["url","html"],
};
function requestOptions(slug:string,options:Options):Record<string,unknown>{
  const keys=[...(inputKeys[slug]||[]),...(slug==="sign"&&options.customPosition?["x","y","w","h"]:[])];
  const values=Object.fromEntries(keys.map(key=>[key,options[key]]));
  if(slug==="redact"&&typeof values.texts==="string")values.texts=values.texts.split(/\r?\n/).filter(Boolean).join(",");
  return values;
}
function filename(slug:string,blob:Blob){const type=blob.type;const extension=type.includes("zip")?"zip":slug==="pdf-to-word"?"docx":slug==="pdf-to-excel"?"xlsx":slug==="pdf-to-ppt"?"pptx":slug==="pdf-to-markdown"?"md":type.includes("jpeg")?"jpg":"pdf";return `pdf-toolkit-${slug}.${extension}`;}
function selectedPages(value:string,total:number){const selected=new Set<number>();for(const part of value.split(",")){const match=part.trim().match(/^(\d+)(?:\s*-\s*(\d+))?$/);if(!match)continue;const start=Number(match[1]),end=Number(match[2]||match[1]);for(let n=start;n<=Math.min(end,total);n++)if(n>0)selected.add(n);}return selected;}
function size(bytes:number){return bytes<1024*1024?`${Math.max(1,Math.round(bytes/1024))} KB`:`${(bytes/1024/1024).toFixed(1)} MB`;}

export function ToolWorkspace({slug:rawSlug,locale}:{slug:string;locale:string}){
  const slug=rawSlug==="repair"?"repair-pdf":rawSlug==="pdfa"?"pdf-to-pdfa":rawSlug;
  const language=locale==="ru"?"ru":"en";
  const t=(ru:string,en:string)=>language==="ru"?ru:en;
  const tool=getTool(slug);
  const [files,setFiles]=useState<File[]>([]);
  const [options,setOptions]=useState<Options>(()=>defaultOptions(slug));
  const [pages,setPages]=useState<PageItem[]>([]);
  const [previewLoading,setPreviewLoading]=useState(false);
  const [previewError,setPreviewError]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [progress,setProgress]=useState("");
  const [result,setResult]=useState<{url:string;name:string;bytes:number}|null>(null);
  const [comparison,setComparison]=useState<Comparison|null>(null);
  const [items,setItems]=useState<EditItem[]>([]);
  const [formValues,setFormValues]=useState<Record<string,string|boolean>>({});
  const [editorImage,setEditorImage]=useState<File>();
  const [workflow,setWorkflow]=useState<WorkflowStep[]>([{id:1,slug:"compress",options:defaultOptions("compress")}]);
  const [dragId,setDragId]=useState<string|null>(null);
  const [pageLimit,setPageLimit]=useState(50);
  const knownFiles=useRef(new Map<File,number>());
  const nextId=useRef(1);
  const resultRef=useRef<HTMLDivElement>(null);
  const sorted=["merge","organize-pdf"].includes(slug);
  const selectable=["split","delete","extract-pages"].includes(slug);
  const editor=["edit-pdf","pdf-forms"].includes(slug);
  const images=["jpg-to-pdf","scan-to-pdf"].includes(slug);
  const multiple=sorted||images||slug==="rotate"||slug==="compare";
  const selection=selectedPages(String(options.pages||""),pages.length);
  const invalidates=()=>{setResult(null);setComparison(null);setError("");};
  useEffect(()=>()=>{if(result)URL.revokeObjectURL(result.url);},[result]);
  useEffect(()=>{if(result||comparison)resultRef.current?.scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches?"auto":"smooth",block:"nearest"});},[result,comparison]);
  useEffect(()=>{
    const controller=new AbortController();
    setPreviewError("");
    setPages(existing=>existing.filter(page=>files.includes(page.file)));
    if(!files.length||images||["word-to-pdf","excel-to-pdf","ppt-to-pdf","html-to-pdf","unlock","compare"].includes(slug)){setPreviewLoading(false);return()=>controller.abort();}
    const newFiles=files.filter(file=>!knownFiles.current.has(file));
    if(!newFiles.length){setPreviewLoading(false);return()=>controller.abort();}
    setPreviewLoading(true);
    (async()=>{
      for(const file of newFiles){
        try{
          const preview=await previewPdf(file,0,controller.signal);
          if(controller.signal.aborted)return;
          const id=nextId.current++;
          knownFiles.current.set(file,id);
          const loaded=new Map(preview.pages.map(page=>[page.page,page]));
          const entries=Array.from({length:preview.numPages},(_,page)=>({page,thumb:"",...loaded.get(page),id:`${id}-${page}`,file,rotation:0}));
          setPages(previous=>[...previous,...entries]);
        }catch(e){if(!controller.signal.aborted)setPreviewError(e instanceof Error?e.message:String(e));}
      }
      if(!controller.signal.aborted)setPreviewLoading(false);
    })();
    return()=>controller.abort();
  },[files,images,slug]);
  const changeOption=(key:string,value:string|boolean|File)=>{setOptions(previous=>({...previous,[key]:value}));invalidates();};
  const addFiles=(incoming:File[])=>{
    invalidates();setItems([]);setFormValues({});setEditorImage(undefined);
    if(slug==="compare"&&files.length+incoming.length>2){setError(t("Для сравнения нужны ровно два файла.","Choose exactly two files to compare."));return;}
    if(!multiple){knownFiles.current.clear();setPages([]);setFiles(incoming.slice(0,1));return;}
    setFiles(previous=>slug==="compare"?[...previous,...incoming].slice(0,2):[...previous,...incoming]);
  };
  const removeFile=(index:number)=>{invalidates();const removed=files[index];knownFiles.current.delete(removed);setFiles(previous=>previous.filter((_,i)=>i!==index));setItems([]);setFormValues({});};
  const movePage=(id:string,target:number)=>{invalidates();setPages(previous=>{const from=previous.findIndex(page=>page.id===id);if(from<0||target<0||target>=previous.length)return previous;const next=[...previous];next.splice(target,0,...next.splice(from,1));return next;});};
  const loadMore=async()=>{
    setPreviewLoading(true);setPreviewError("");
    try{
      for(const file of files){const pending=pages.find(page=>page.file===file&&!page.thumb);if(!pending)continue;const data=await previewPdf(file,pending.page);const updated=new Map(data.pages.map(page=>[page.page,page]));setPages(previous=>previous.map(page=>page.file===file&&updated.has(page.page)?{...page,...updated.get(page.page)}:page));break;}
      setPageLimit(previous=>previous+50);
    }catch(e){setPreviewError(e instanceof Error?e.message:String(e));}finally{setPreviewLoading(false);}
  };
  const execute=async(e:React.FormEvent)=>{
    e.preventDefault();if(busy)return;invalidates();
    if(!files.length&&!(slug==="html-to-pdf"&&(options.url||options.html))){setError(t("Сначала добавьте файл.","Add a file first."));return;}
    if(slug==="compare"&&files.length!==2){setError(t("Добавьте два PDF для сравнения.","Add two PDFs to compare."));return;}
    if(sorted&&(!pages.length||files.some(file=>!knownFiles.current.has(file)))){setError(t("Не удалось прочитать страницы всех файлов. Удалите повреждённый файл и попробуйте снова.","Could not read all files. Remove the invalid file and try again."));return;}
    if(slug==="watermark"&&!options.text&&!options.image){setError(t("Введите текст или добавьте изображение водяного знака.","Enter watermark text or add an image."));return;}
    if(slug==="sign"&&!options.image){setError(t("Загрузите или нарисуйте подпись.","Upload or draw your signature."));return;}
    if(slug==="redact"&&!options.texts&&!options.hide_images){setError(t("Укажите текст или выберите удаление изображений.","Enter text or select image removal."));return;}
    if(slug==="edit-pdf"&&!items.length){setError(t("Добавьте текст, изображение или рисунок на страницу.","Add text, an image or a drawing to the page."));return;}
    if(slug==="pdf-forms"&&!items.length&&!Object.keys(formValues).length){setError(t("Заполните хотя бы одно поле или создайте новое на странице.","Fill at least one field or create a new one on the page."));return;}
    setBusy(true);setProgress(t("Обрабатываем документ…","Processing your document…"));
    try{
      if(slug==="compare"){setComparison(await callCompare(files[0],files[1]));return;}
      let blob:Blob;
      if(slug==="workflows"){
        if(!workflow.length)throw new Error(t("Добавьте хотя бы один шаг.","Add at least one step."));
        let current=files[0];
        for(let i=0;i<workflow.length;i++){
          const step=workflow[i];
          if(step.slug==="protect"&&i<workflow.length-1)throw new Error(t("Защиту паролем поставьте последним шагом.","Password protection must be the last step."));
          setProgress(`${t("Шаг","Step")} ${i+1} / ${workflow.length}: ${getTool(step.slug)?.title[language]||step.slug}`);
          const output=await callTool(step.slug,[current],requestOptions(step.slug,step.options));
          if(!output.type.includes("pdf"))throw new Error(t("Этот шаг не вернул PDF.","This step did not return a PDF."));
          current=new File([output],"workflow.pdf",{type:"application/pdf"});
        }
        blob=current;
      }else{
        const opts=requestOptions(slug,options);
        if(sorted)opts.order=pages.map(page=>({file:files.indexOf(page.file),page:page.page+(slug==="organize-pdf"?1:0),...(slug==="organize-pdf"?{rotation:page.rotation}:{})}));
        if(slug==="edit-pdf"){opts.operations=items;if(editorImage)opts.image=editorImage;}
        if(slug==="pdf-forms"){opts.fields=items;opts.values=formValues;}
        blob=await callTool(slug==="scan-to-pdf"?"jpg-to-pdf":slug,files,opts);
      }
      setResult({url:URL.createObjectURL(blob),name:filename(slug,blob),bytes:blob.size});
    }catch(e){const detail=e instanceof Error?e.message:String(e);setError(/Failed to fetch|fetch failed/i.test(detail)?t("Сервер недоступен. Проверьте подключение и попробуйте снова.","The server is unavailable. Check your connection and try again."):detail);}finally{setBusy(false);setProgress("");}
  };
  if(!tool)return <main className="tool-workspace"><h1>{t("Инструмент не найден","Tool not found")}</h1><Link href={`/${language}`}>{t("Все инструменты","All tools")}</Link></main>;
  const activeStep=result||comparison?3:files.length||(slug==="html-to-pdf"&&(options.url||options.html))?2:1;
  return <main className="tool-workspace">
    <Link className="workspace-back" href={`/${language}`}><Icon name="arrow-left" size={16}/>{t("Все инструменты","All tools")}</Link>
    <header className="tool-heading"><div className={`tool-heading-icon ${tool.color}`}><Icon name={tool.icon} size={30}/></div><div><div className="workspace-eyebrow">PDF TOOLKIT <span> / </span> {t("РАБОЧЕЕ ПРОСТРАНСТВО","WORKSPACE")}</div><h1>{tool.title[language]}</h1><p>{tool.description[language]}</p></div></header>
    <ol className="workspace-stepper" aria-label={t("Этапы работы","Steps")}>{[t("Добавьте файл","Add a file"),t("Настройте результат","Make it yours"),t("Скачайте готовое","Download result")].map((label,index)=><li key={label} className={activeStep===index+1?"current":activeStep>index+1?"complete":""} aria-current={activeStep===index+1?"step":undefined}><span>{activeStep>index+1?<Icon name="check" size={14}/>:index+1}</span>{label}</li>)}</ol>
    <form onSubmit={execute} className="workspace-grid">
      <section className="workspace-panel"><div className="workspace-panel-heading"><div><h2>{files.length?t("Ваши файлы","Your files"):t("Всё начинается с файла","Start with your file")}</h2><p>{files.length?`${files.length} ${t("файл(ов)","file(s)")} · ${size(files.reduce((sum,file)=>sum+file.size,0))}`:slug==="html-to-pdf"?t("Загрузите HTML или вставьте адрес в настройках.","Upload HTML or enter a URL in the settings."):t("Добавьте документ — мы покажем следующий шаг.","Add your document and we’ll guide you from there.")}</p></div>{files.length>0&&!busy&&<button className="text-action" type="button" onClick={()=>{invalidates();knownFiles.current.clear();setFiles([]);setPages([]);setItems([]);setFormValues({});}}>{t("Очистить","Clear")}</button>}</div>
        <fieldset disabled={busy} className="workspace-inputs">
        <DropZone onFiles={addFiles} maxFiles={slug==="compare"?Math.max(1,2-files.length):multiple?undefined:1} multiple={multiple} accept={getAcceptForSlug(images?"jpg-to-pdf":slug)}/>
        {slug==="scan-to-pdf"&&<label className="camera-upload btn-secondary"><Icon name="scan" size={18}/>{t("Сфотографировать документ","Take a photo")}<input type="file" accept="image/*" capture="environment" onChange={e=>e.target.files&&addFiles(Array.from(e.target.files))}/></label>}
        {files.length>0&&<ul className="workspace-files">{files.map((file,i)=><li key={`${file.name}-${i}`}><span className="workspace-file-icon"><Icon name={images?"image":"file"} size={20}/></span><div><strong>{file.name}</strong><small>{slug==="compare"?`${i===0?t("Оригинал","Original"):t("Новая версия","New version")} · `:""}{size(file.size)}</small></div>{multiple&&!sorted&&<><button type="button" className="icon-button" disabled={i===0} aria-label={t("Переместить файл выше","Move file up")} onClick={()=>{invalidates();setFiles(previous=>{const next=[...previous];[next[i-1],next[i]]=[next[i],next[i-1]];return next;});}}><Icon name="chevron-left" size={15}/></button><button type="button" className="icon-button" disabled={i===files.length-1} aria-label={t("Переместить файл ниже","Move file down")} onClick={()=>{invalidates();setFiles(previous=>{const next=[...previous];[next[i+1],next[i]]=[next[i],next[i+1]];return next;});}}><Icon name="chevron-right" size={15}/></button></>}<button type="button" className="icon-button" onClick={()=>removeFile(i)} aria-label={`${t("Удалить","Remove")} ${file.name}`}><Icon name="close" size={17}/></button></li>)}</ul>}
        {previewError&&<div className="preview-warning" role="status">{t("Предпросмотр недоступен: ","Preview unavailable: ")}{previewError}</div>}
        {previewLoading&&<p className="preview-loading" role="status"><span className="workspace-spinner"/>{t("Подготавливаем страницы…","Preparing pages…")}</p>}
        {pages.length>0&&<><div className="page-grid-heading"><h3>{editor?t("Редактор документа","Document editor"):`${t("Страницы","Pages")} · ${pages.length}`}</h3>{selectable&&<div><button type="button" className="text-action" onClick={()=>changeOption("pages",`1-${pages.length}`)}>{t("Выбрать все","Select all")}</button><button type="button" className="text-action" onClick={()=>changeOption("pages","")}>{t("Снять выбор","Deselect")}</button></div>}</div>{editor&&files[0]?<DocumentEditor key={`${files[0].name}-${files[0].lastModified}`} locale={language} file={files[0]} pages={pages.filter(page=>page.thumb)} forms={slug==="pdf-forms"} items={items} onItems={next=>{setItems(next);invalidates();}} values={formValues} onValues={next=>{setFormValues(next);invalidates();}} image={editorImage} onImage={file=>{setEditorImage(file);invalidates();}}/>:<div className="pdf-page-grid">{pages.slice(0,pageLimit).map((page,i)=><article key={page.id} className={`pdf-page-card ${selection.has(page.page+1)&&selectable?"selected":""} ${dragId===page.id?"dragging":""}`} draggable={sorted} onDragStart={()=>setDragId(page.id)} onDragOver={e=>sorted&&e.preventDefault()} onDrop={e=>{e.preventDefault();if(dragId)movePage(dragId,i);setDragId(null);}} onDragEnd={()=>setDragId(null)}><button className="pdf-page-preview" type="button" disabled={!selectable} aria-pressed={selectable?selection.has(page.page+1):undefined} aria-label={`${t("Выбрать страницу","Select page")} ${page.page+1}`} onClick={()=>{const next=new Set(selection);next.has(page.page+1)?next.delete(page.page+1):next.add(page.page+1);changeOption("pages",Array.from(next).sort((a,b)=>a-b).join(","));}}>{page.thumb?<img src={page.thumb} alt={`${t("Страница","Page")} ${page.page+1}`} style={{transform:`rotate(${page.rotation+(slug==="rotate"?Number(options.angle):0)}deg)`}} draggable={false}/>:<span className="pdf-page-placeholder"><Icon name="file" size={32}/>{page.page+1}</span>}<PageOverlay slug={slug} options={options} page={page} total={pages.length}/>{selectable&&<span className="page-check">{selection.has(page.page+1)&&<Icon name="check" size={12}/>}</span>}</button><div className="page-caption"><strong>{page.page+1}</strong>{sorted&&<small title={page.file.name}>{page.file.name}</small>}</div>{sorted&&<div className="page-controls"><button type="button" className="icon-button" disabled={i===0} onClick={()=>movePage(page.id,i-1)} aria-label={t("Страницу влево","Move page left")}><Icon name="chevron-left" size={14}/></button><button type="button" className="icon-button" disabled={i===pages.length-1} onClick={()=>movePage(page.id,i+1)} aria-label={t("Страницу вправо","Move page right")}><Icon name="chevron-right" size={14}/></button>{slug==="organize-pdf"&&<><button type="button" className="icon-button" onClick={()=>{invalidates();setPages(previous=>previous.map(item=>item.id===page.id?{...item,rotation:(item.rotation+90)%360}:item));}} aria-label={t("Повернуть страницу","Rotate page")}><Icon name="rotate" size={14}/></button><button type="button" className="icon-button" disabled={pages.length===1} onClick={()=>{invalidates();setPages(previous=>previous.filter(item=>item.id!==page.id));}} aria-label={t("Удалить страницу","Delete page")}><Icon name="trash" size={14}/></button></>}</div>}</article>)}</div>}{(pages.some(page=>!page.thumb)||pages.length>pageLimit)&&<button type="button" className="btn-secondary load-pages" disabled={previewLoading} onClick={loadMore}>{t("Показать ещё страницы","Show more pages")}</button>}</>}
        {!files.length&&<div className="workspace-empty"><div className="empty-paper"><span/><span/><span/><span/></div><div><strong>{t("Ваш документ появится здесь","Your document will appear here")}</strong><p>{t("Оригинал останется на вашем устройстве.","Your original stays on your device.")}</p></div></div>}
        </fieldset>
      </section>
      <aside className="options-panel"><div className="options-heading"><span><Icon name="settings" size={18}/></span><div><h2>{t("Настройки","Settings")}</h2><p>{t("Немного деталей — и готово","A few details and you’re ready")}</p></div></div><fieldset disabled={busy} className="workspace-inputs">
        {slug==="workflows"?<div className="workflow-builder"><p className="option-note">{t("Шаги выполняются последовательно. Результат каждого передаётся следующему.","Steps run in order. Each result is passed to the next step.")}</p>{workflow.map((step,i)=><div className="workflow-step" key={step.id}><div className="workflow-step-heading"><b>{i+1}</b><select aria-label={t("Инструмент шага","Step tool")} value={step.slug} onChange={e=>{invalidates();setWorkflow(previous=>previous.map(item=>item.id===step.id?{...item,slug:e.target.value,options:defaultOptions(e.target.value)}:item));}}>{workflowTools.map(name=><option key={name} value={name}>{getTool(name)?.title[language]||name}</option>)}</select><button className="icon-button" type="button" aria-label={t("Удалить шаг","Remove step")} onClick={()=>{invalidates();setWorkflow(previous=>previous.filter(item=>item.id!==step.id));}}><Icon name="close" size={16}/></button></div><ToolOptions slug={step.slug} locale={language} options={step.options} onChange={(key,value)=>{invalidates();setWorkflow(previous=>previous.map(item=>item.id===step.id?{...item,options:{...item.options,[key]:value}}:item));}}/></div>)}<button className="btn-secondary" type="button" disabled={workflow.length>=6} onClick={()=>{invalidates();setWorkflow(previous=>[...previous,{id:Date.now(),slug:"rotate",options:defaultOptions("rotate")}]);}}><Icon name="plus" size={17}/>{t("Добавить шаг","Add step")}</button></div>:editor?<p className="option-note">{slug==="pdf-forms"?t("Заполните существующие поля или добавьте новые на странице. Они останутся интерактивными в готовом PDF.","Fill existing fields or add new ones on the page. They remain interactive in the resulting PDF."):t("Добавляйте текст, изображения, фигуры и рисунки поверх страниц. Изменения видны сразу в редакторе.","Add text, images, shapes and drawings over your pages. Preview changes directly in the editor.")}</p>:<ToolOptions slug={slug} locale={language} options={options} onChange={changeOption}/>}
        </fieldset>
        {error&&<div className="workspace-error" role="alert"><strong>{t("Не получилось обработать файл","We couldn’t process this file")}</strong><p>{error}</p></div>}
        <button className="btn-primary workspace-submit" type="submit" disabled={busy||(!files.length&&!(slug==="html-to-pdf"&&(options.url||options.html)))||(sorted&&previewLoading)}>{busy?<><span className="workspace-spinner"/>{t("Обработка…","Processing…")}</>:<>{slug==="compare"?t("Сравнить документы","Compare documents"):slug==="workflows"?t("Запустить обработку","Run workflow"):t("Создать результат","Create result")}<Icon name="arrow-right" size={18}/></>}</button>
        {busy&&<p className="processing-status" role="status" aria-live="polite">{progress}</p>}
        <p className="workspace-privacy"><Icon name="shield" size={15}/>{t("Файлы обрабатывает сервер PDF Toolkit","Files are processed by the PDF Toolkit server")}</p>
      </aside>
    </form>
    <div ref={resultRef}>
      {result&&<section className="result-panel" aria-live="polite"><span className="result-check"><Icon name="check" size={25}/></span><div><p className="workspace-eyebrow">{t("ГОТОВО К СКАЧИВАНИЮ","READY TO DOWNLOAD")}</p><h2>{t("Всё готово. Отличная работа!","All done. Nicely handled!")}</h2><p>{result.name} · {size(result.bytes)}{slug==="compress"&&files[0]&&result.bytes<files[0].size?` · −${Math.round((1-result.bytes/files[0].size)*100)}%`:""}</p></div><a className="btn-primary" href={result.url} download={result.name}><Icon name="download" size={19}/>{t("Скачать файл","Download file")}</a></section>}
      {comparison&&<section className="comparison-panel"><h2>{t("Результат сравнения","Comparison results")}</h2><p>{comparison.pages.filter(page=>page.diff).length} / {comparison.pages.length} {t("страниц с отличиями","pages differ")}</p>{comparison.pages.map(page=><article className={`comparison-page ${page.diff?"has-diff":""}`} key={page.index}><h3>{t("Страница","Page")} {page.index+1} <span>{page.diff?t("Есть отличия","Changed"):t("Без изменений","Unchanged")}</span></h3><div>{[[page.left_thumb,page.left_text,t("Оригинал","Original")],[page.right_thumb,page.right_text,t("Новая версия","New version")]].map(([thumb,text,label])=><section key={label}><h4>{label}</h4>{thumb&&<img src={thumb.startsWith("data:")?thumb:`data:image/png;base64,${thumb}`} alt={label}/>}<details><summary>{t("Текст страницы","Page text")}</summary><pre>{text||t("Нет текста","No text")}</pre></details></section>)}</div></article>)}</section>}
    </div>
  </main>;
}

