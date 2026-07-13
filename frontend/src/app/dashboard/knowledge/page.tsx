"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { api, ApiError } from "@/lib/api";
import type { DocumentOut } from "@/lib/types";
import { toast } from "sonner";

const STATUS_VARIANT: Record<DocumentOut["status"], "default" | "secondary" | "destructive"> = {
  ready: "default",
  processing: "secondary",
  failed: "destructive",
};

export default function KnowledgeBasePage() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<"text" | "pdf">("text");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function loadDocuments() {
    setLoading(true);
    try {
      const docs = await api.get<DocumentOut[]>("/documents");
      setDocuments(docs);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "pdf" && !file) {
      toast.error("Choose a PDF file first.");
      return;
    }
    setSubmitting(true);
    try {
      if (mode === "pdf" && file) {
        const formData = new FormData();
        formData.append("title", title);
        formData.append("file", file);
        await api.postFile("/documents/upload", formData);
      } else {
        await api.post("/documents", { title, text });
      }
      toast.success("Document uploaded");
      setTitle("");
      setText("");
      setFile(null);
      await loadDocuments();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/documents/${id}`);
      toast.success("Document deleted");
      setDocuments((docs) => docs.filter((d) => d.id !== id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-on-surface">Knowledge Base</h1>
        <p className="text-sm text-on-surface-variant">
          Upload the FAQs, prices, and policies the assistant should answer from.
        </p>
      </div>

      <Card className="border-outline-variant/60">
        <CardContent className="p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded bg-surface-container text-on-surface-variant">
                <Icon name="folder_data" size={18} />
              </div>
              <h2 className="text-sm font-semibold text-on-surface">Upload a document</h2>
            </div>
            <div className="flex gap-1 rounded-lg border border-outline-variant/60 p-0.5">
              <button
                type="button"
                onClick={() => setMode("text")}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  mode === "text" ? "bg-primary-container/30 text-on-surface" : "text-on-surface-variant"
                }`}
              >
                Paste text
              </button>
              <button
                type="button"
                onClick={() => setMode("pdf")}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                  mode === "pdf" ? "bg-primary-container/30 text-on-surface" : "text-on-surface-variant"
                }`}
              >
                Upload PDF
              </button>
            </div>
          </div>
          <form onSubmit={handleUpload} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="doc-title">Title</Label>
              <Input
                id="doc-title"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Clinic FAQ"
              />
            </div>
            {mode === "text" ? (
              <div className="flex flex-col gap-2">
                <Label htmlFor="doc-text">Content</Label>
                <Textarea
                  id="doc-text"
                  required
                  rows={8}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste the FAQ, pricing, timings, location, etc."
                />
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <Label htmlFor="doc-file">PDF file</Label>
                <Input
                  id="doc-file"
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <p className="text-xs text-on-surface-variant">
                  Text-based PDFs only -- scanned/image PDFs without a text layer aren&apos;t
                  supported yet. Max 10MB.
                </p>
              </div>
            )}
            <Button type="submit" disabled={submitting} className="w-fit">
              {submitting ? "Uploading..." : "Upload"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
          Active Documents
        </h2>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No documents uploaded yet.</p>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-lg border border-outline-variant/50 bg-surface p-3 transition-shadow duration-150 hover:shadow-sm"
            >
              <div className="flex items-center gap-3">
                <Icon name="description" size={20} className="text-primary" />
                <div>
                  <div className="text-sm font-medium text-on-surface">{doc.title}</div>
                  <Badge variant={STATUS_VARIANT[doc.status]} className="mt-0.5">
                    {doc.status}
                  </Badge>
                </div>
              </div>
              <button
                onClick={() => handleDelete(doc.id)}
                className="p-1 text-on-surface-variant transition-colors hover:text-destructive"
              >
                <Icon name="delete" size={18} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
