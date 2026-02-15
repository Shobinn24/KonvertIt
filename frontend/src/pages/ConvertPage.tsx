import { useState, useEffect } from "react";
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
  const [selectedBulkIndex, setSelectedBulkIndex] = useState<number | null>(null);
  const bulk = useBulkStream();

  // Auto-select first completed item when bulk job finishes
  useEffect(() => {
    if (bulk.state.phase === "done" && !preview) {
      const firstCompleted = bulk.state.items.findIndex(
        (item) => item.status === "completed" && item.result
      );
      if (firstCompleted >= 0) {
        const item = bulk.state.items[firstCompleted];
        if (item?.result) {
          setSelectedBulkIndex(firstCompleted);
          setPreview(item.result as ConversionResult);
        }
      }
    }
  }, [bulk.state.phase, bulk.state.items, preview]);

  const handleBulkItemSelect = (result: unknown) => {
    const idx = bulk.state.items.findIndex((item) => item.result === result);
    setSelectedBulkIndex(idx >= 0 ? idx : null);
    setPreview(result as ConversionResult);
  };

  const handleBulkReset = () => {
    bulk.reset();
    setPreview(null);
    setSelectedBulkIndex(null);
  };

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
                <BulkProgress
                  state={bulk.state}
                  onReset={handleBulkReset}
                  onItemSelect={handleBulkItemSelect}
                  selectedIndex={selectedBulkIndex}
                />
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
