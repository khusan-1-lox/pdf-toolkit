"use client";
import { useCallback, useState } from "react";
import { useDropzone, FileRejection } from "react-dropzone";
import { useParams } from "next/navigation";
import { useLocale } from "next-intl";
import Icon from "./Icon";
const PDF = {"application/pdf":[".pdf"]};
export function getAcceptForSlug(slug?: string): Record<string,string[]> {
  if (["jpg-to-pdf","scan-to-pdf"].includes(slug || "")) return {"image/jpeg":[".jpg",".jpeg"],"image/png":[".png"],"image/webp":[".webp"],"image/bmp":[".bmp"],"image/tiff":[".tiff",".tif"]};
  if (slug === "word-to-pdf") return {"application/vnd.openxmlformats-officedocument.wordprocessingml.document":[".docx"],"application/msword":[".doc"]};
  if (slug === "excel-to-pdf") return {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":[".xlsx"],"application/vnd.ms-excel":[".xls"]};
  if (slug === "ppt-to-pdf") return {"application/vnd.openxmlformats-officedocument.presentationml.presentation":[".pptx"],"application/vnd.ms-powerpoint":[".ppt"]};
  if (slug === "html-to-pdf") return {"text/html":[".html",".htm"]};
  return PDF;
}
export function DropZone({onFiles,maxFiles,multiple=true,accept}:{onFiles:(files:File[])=>void;maxFiles?:number;multiple?:boolean;accept?:Record<string,string[]>}) {
  const [error,setError]=useState<string|null>(null);
  const ru = useLocale() === "ru";
  const params=useParams() as {slug?:string};
  const resolvedAccept=accept ?? getAcceptForSlug(params?.slug);
  const isMultiple = maxFiles ? maxFiles > 1 : multiple;
  const onDrop=useCallback((files:File[],rejections:FileRejection[])=>{
    setError(rejections.length ? rejections.map(r => `${r.file.name}: ` + r.errors.map(e => e.code === "too-many-files" && maxFiles ? (ru ? `не более ${maxFiles} файлов` : `up to ${maxFiles} files`) : (ru ? "неподдерживаемый формат" : "unsupported format")).join(", ")).join("; ") : null);
    if(files.length) onFiles(files);
  },[onFiles,maxFiles,ru]);
  const {getRootProps,getInputProps,isDragActive,isDragReject}=useDropzone({onDrop,accept:resolvedAccept,maxFiles,multiple:isMultiple});
  const extensions=Array.from(new Set(Object.values(resolvedAccept).flat())).map(s=>s.slice(1).toUpperCase()).join(", ");
  return <div><div {...getRootProps()} className={`drop-zone ${isDragReject ? "drag-reject" : isDragActive ? "drag-active" : ""}`}><input {...getInputProps()} /><div className="upload-orb"><Icon name="upload" size={27}/></div><h3>{isDragActive ? (ru ? "Отпустите файлы здесь" : "Drop your files here") : (ru ? "Перетащите файлы сюда" : "Drop your files here")}</h3><p>{ru ? "или выберите их на устройстве" : "or choose them from your device"}</p><span className="upload-action"><Icon name="plus" size={15}/>{ru ? "Выбрать файлы" : "Choose files"}</span><span className="upload-limits">{extensions} · {ru ? "без ограничений" : "no limits"}</span></div>{error && <p role="alert" className="upload-error">{error}</p>}</div>;
}
export default DropZone;
