import { useState } from "react";
import { TopBar } from "@/components/layout/TopBar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SingleConvert } from "@/components/convert/SingleConvert";
import { BulkConvert } from "@/components/convert/BulkConvert";
import { PreviewPanel } from "@/components/convert/PreviewPanel";
import { BulkProgress } from "@/components/convert/BulkProgress";
import { useBulkStream } from "@/hooks/useBulkStream";
import type { ConversionResult } from "@/types/api";

export function ConvertPage() {
  const [preview, setPreview] = useState<ConversionResult | null>(null);
  const bulk = useBulkStream();

  return (
    <>
      <TopBar title="Convert" />
      <div className="space-y-6 p-6">
        <div className="grid gap-6 lg:grid-cols-5">
          {/* Left column: conversion forms */}
          <div className="space-y-6 lg:col-span-3">
            <Tabs defaultValue="single">
              <TabsList>
                <TabsTrigger value="single">Single</TabsTrigger>
                <TabsTrigger value="bulk">Bulk</TabsTrigger>
              </TabsList>

              <TabsContent value="single">
                <SingleConvert onResult={setPreview} />
              </TabsContent>

              <TabsContent value="bulk" className="space-y-4">
                <BulkConvert
                  onStart={bulk.start}
                  onCancel={bulk.cancel}
                  isStreaming={bulk.state.phase === "streaming"}
                />
                <BulkProgress state={bulk.state} onReset={bulk.reset} />
              </TabsContent>
            </Tabs>
          </div>

          {/* Right column: preview panel */}
          <div className="lg:col-span-2">
            <PreviewPanel result={preview} />
          </div>
        </div>
      </div>
    </>
  );
}
