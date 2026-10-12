"use client";
import { useLocale } from "next-intl";
import Icon from "./Icon";
export function formatSize(bytes:number):string {return bytes<1024 ? `${bytes} B` : bytes<1048576 ? `${(bytes/1024).toFixed(1)} KB` : `${(bytes/1048576).toFixed(1)} MB`;}
export function FileList({files,onRemove}:{files:File[];onRemove:(index:number)=>void}) {
  const ru=useLocale()==="ru";
  if(!files.length) return null;
  return <ul className="file-list">{files.map((file,i)=><li key={`${file.name}-${i}`} className="file-row"><span className="file-format"><Icon name={file.type.startsWith("image/")?"image":"file"} size={20}/></span><div><strong>{file.name}</strong><small>{formatSize(file.size)} · {file.name.split(".").pop()?.toUpperCase()}</small></div><button type="button" className="icon-button" onClick={()=>onRemove(i)} aria-label={`${ru?"Удалить":"Remove"} ${file.name}`}><Icon name="close" size={14}/></button></li>)}</ul>;
}
export default FileList;
