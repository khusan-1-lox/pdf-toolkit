"use client";
import {ToolWorkspace} from "@/components/ToolWorkspace";
export default function ToolPage({params}:{params:{locale:string;slug:string}}){
  return <ToolWorkspace key={`${params.locale}-${params.slug}`} locale={params.locale} slug={params.slug}/>;
}
