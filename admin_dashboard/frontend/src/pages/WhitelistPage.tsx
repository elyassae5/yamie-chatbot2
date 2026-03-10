import { useState, useEffect } from "react";
import Layout from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Plus, Trash2, Power, PowerOff } from "lucide-react";
import type { WhitelistEntry } from "@/api/whitelist";
import {
  getWhitelist,
  addWhitelistEntry,
  updateWhitelistEntry,
  deleteWhitelistEntry,
} from "@/api/whitelist";

export default function WhitelistPage() {
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    phone_number: "",
    name: "",
    department: "",
    notes: "",
  });

  useEffect(() => {
    loadWhitelist();
  }, []);

  const loadWhitelist = async () => {
    try {
      setLoading(true);
      const data = await getWhitelist();
      setEntries(data);
      setError("");
    } catch (err) {
      setError("Kon whitelist niet laden");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addWhitelistEntry(formData);
      setDialogOpen(false);
      setFormData({ phone_number: "", name: "", department: "", notes: "" });
      loadWhitelist();
    } catch (err) {
      setError("Kon nummer niet toevoegen");
    }
  };

  const handleToggleActive = async (entry: WhitelistEntry) => {
    try {
      await updateWhitelistEntry(entry.id, { is_active: !entry.is_active });
      loadWhitelist();
    } catch (err) {
      setError("Kon status niet wijzigen");
    }
  };

  const handleDelete = async (entryId: string) => {
    if (!confirm("Weet je zeker dat je dit nummer wilt verwijderen?")) return;
    try {
      await deleteWhitelistEntry(entryId);
      loadWhitelist();
    } catch (err) {
      setError("Kon nummer niet verwijderen");
    }
  };

  return (
    <Layout>
      <div>
        {/* Header */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
              Telefoonnummers
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Beheer wie toegang heeft tot de bot
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-1" />
                Toevoegen
              </Button>
            </DialogTrigger>
            <DialogContent className="w-[95vw] max-w-md mx-auto">
              <DialogHeader>
                <DialogTitle>Nummer Toevoegen</DialogTitle>
                <DialogDescription>
                  Voeg een nieuw nummer toe aan de whitelist
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleAdd} className="space-y-4">
                <div>
                  <Label htmlFor="phone_number">Telefoonnummer *</Label>
                  <Input
                    id="phone_number"
                    placeholder="+31612345678"
                    value={formData.phone_number}
                    onChange={(e) =>
                      setFormData({ ...formData, phone_number: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="name">Naam *</Label>
                  <Input
                    id="name"
                    placeholder="Jan Jansen"
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="department">Afdeling *</Label>
                  <Input
                    id="department"
                    placeholder="Manager"
                    value={formData.department}
                    onChange={(e) =>
                      setFormData({ ...formData, department: e.target.value })
                    }
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="notes">Notities</Label>
                  <Input
                    id="notes"
                    placeholder="Extra informatie (optioneel)"
                    value={formData.notes}
                    onChange={(e) =>
                      setFormData({ ...formData, notes: e.target.value })
                    }
                  />
                </div>
                <Button type="submit" className="w-full">
                  Toevoegen
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="text-center py-12 text-gray-500">
            Bezig met laden...
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            Geen nummers in de whitelist
          </div>
        ) : (
          <>
            {/* Mobile: Card list */}
            <div className="sm:hidden space-y-3">
              {entries.map((entry) => (
                <div key={entry.id} className="bg-white shadow rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-semibold text-gray-900">
                        {entry.name}
                      </p>
                      <p className="text-xs font-mono text-gray-500 mt-0.5">
                        {entry.phone_number}
                      </p>
                      {entry.department && (
                        <p className="text-sm text-gray-600 mt-1">
                          {entry.department}
                        </p>
                      )}
                    </div>
                    <Badge
                      variant={entry.is_active ? "default" : "secondary"}
                      className="ml-2 shrink-0"
                    >
                      {entry.is_active ? "Actief" : "Inactief"}
                    </Badge>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleToggleActive(entry)}
                    >
                      {entry.is_active ? (
                        <>
                          <PowerOff className="h-4 w-4 mr-1" /> Deactiveren
                        </>
                      ) : (
                        <>
                          <Power className="h-4 w-4 mr-1" /> Activeren
                        </>
                      )}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="flex-1"
                      onClick={() => handleDelete(entry.id)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" /> Verwijderen
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop: Table */}
            <div className="hidden sm:block bg-white shadow rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Naam</TableHead>
                    <TableHead>Telefoonnummer</TableHead>
                    <TableHead>Afdeling</TableHead>
                    <TableHead>Toegevoegd</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Acties</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="font-medium">
                        {entry.name}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {entry.phone_number}
                      </TableCell>
                      <TableCell>{entry.department}</TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(entry.added_at).toLocaleDateString("nl-NL")}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={entry.is_active ? "default" : "secondary"}
                        >
                          {entry.is_active ? "Actief" : "Inactief"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleToggleActive(entry)}
                          >
                            {entry.is_active ? (
                              <PowerOff className="h-4 w-4" />
                            ) : (
                              <Power className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDelete(entry.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </div>
    </Layout>
  );
}
