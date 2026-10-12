"use client";
import {useEffect,useState} from "react";
import {PreviewPage} from "@/lib/api";
import {Options} from "./ToolOptions";

/** An approximate placement preview; PDF font metrics can differ slightly. */
export function PageOverlay({slug,options,page,total}:{slug:string;options:Options;page:PreviewPage;total:number}){
  const [image,setImage]=useState<{url:string;width:number;height:number}|null>(null);
  useEffect(()=>{
    if(!(options.image instanceof Blob)){setImage(null);return;}
    const url=URL.createObjectURL(options.image),img=new Image();let active=true;
    img.onload=()=>{if(active)setImage({url,width:img.naturalWidth,height:img.naturalHeight});};img.src=url;
    return()=>{active=false;URL.revokeObjectURL(url);};
  },[options.image]);
  if(!["watermark","page-numbers","sign","crop"].includes(slug))return null;
  const width=page.width||595,height=page.height||842;
  const position=String(options.position||"center"),margin=slug==="page-numbers"?Number(options.margin)||20:20;
  const isLeft=position.endsWith("left"),isRight=position.endsWith("right"),isTop=position.startsWith("top"),isBottom=position.startsWith("bottom");
  const fontSize=Number(options.fontSize)||12;
  const x=isLeft?margin:isRight?width-margin:width/2,y=isTop?margin+fontSize:isBottom?height-margin:height/2+fontSize*.3;
  let content:React.ReactNode=null;
  if(slug==="crop"){
    const multiplier=options.unit==="mm"?2.83464567:1;
    const v=(key:string)=>Math.max(0,Number(options[key])||0)*multiplier;
    const left=options.mode==="rect"?v("x"):v("left"),top=options.mode==="rect"?v("y"):v("top");
    const w=options.mode==="rect"?v("w"):width-left-v("right"),h=options.mode==="rect"?v("h"):height-top-v("bottom");
    content=<><path d={`M0 0H${width}V${height}H0Z M${left} ${top}V${top+h}H${left+w}V${top}Z`} fill="#7055e8" fillOpacity=".2" fillRule="evenodd"/><rect x={left} y={top} width={Math.max(0,w)} height={Math.max(0,h)} fill="none" stroke="#7055e8" strokeWidth="3" strokeDasharray="8 5"/></>;
  }else if(slug==="page-numbers"){
    const number=(Number(options.startNumber)||1)+page.page;
    const format=String(options.format||"1");
    const text=format==="1 / N"?`${number} / ${total}`:format==="Page 1"?`Page ${number}`:format==="Page 1 of N"?`Page ${number} of ${total}`:String(number);
    content=<text x={x} y={y} textAnchor={isLeft?"start":isRight?"end":"middle"} fill={String(options.color)} fontSize={fontSize} fontFamily="Arial,sans-serif">{text}</text>;
  }else{
    let imageWidth=image?Math.min(slug==="sign"?150:width*.3,image.width*.5):0;
    let imageHeight=image?imageWidth*image.height/image.width:0;
    const scale=Math.min(1,height*.5/imageHeight,width*.5/imageWidth);imageWidth*=scale;imageHeight*=scale;
    const ix=options.customPosition?Number(options.x):isLeft?margin:isRight?width-margin-imageWidth:(width-imageWidth)/2;
    const iy=options.customPosition?Number(options.y):isTop?margin:isBottom?height-margin-imageHeight:(height-imageHeight)/2;
    content=<g opacity={Number(options.opacity)||1}>{slug==="watermark"&&options.text&&<text x={x} y={y} textAnchor={isLeft?"start":isRight?"end":"middle"} fill={String(options.color)} fontSize={fontSize} fontFamily="Arial,sans-serif" transform={`rotate(${-Number(options.rotation)||0},${x},${y})`}>{String(options.text)}</text>}{image&&<image href={image.url} x={ix} y={iy} width={options.customPosition?Number(options.w):imageWidth} height={options.customPosition?Number(options.h):imageHeight} preserveAspectRatio="xMidYMid meet"/>}</g>;
  }
  return <svg className="page-live-overlay" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">{content}</svg>;
}
