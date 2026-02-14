import { useState, useEffect } from 'react';
import Layout from '@/components/Layout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Plus, Trash2, Power, PowerOff } from 'lucide-react';
import type { WhitelistEntry } from '@/api/whitelist';
import {
  getWhitelist,
  addWhitelistEntry,
  updateWhitelistEntry,
  deleteWhitelistEntry,
} from '@/api/whitelist';

export default function WhitelistPage() {
  const [entries, setEntries] = useState<WhitelistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    phone_number: '',
    name: '',
    department: '',
    notes: '',
  });

  // Load whitelist on mount
  useEffect(() => {
    loadWhitelist();
  }, []);

  const loadWhitelist = async () => {
    try {
      setLoading(true);
      const data = await getWhitelist();
      setEntries(data);
      setError('');
    } catch (err) {
      setError('Kon whitelist niet laden');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addWhitelistEntry(formData);
      setDialogOpen(false);
      setFormData({ phone_number: '', name: '', department: '', notes: '' });
      loadWhitelist();
    } catch (err) {
      setError('Kon nummer niet toevoegen');
      console.error(err);
    }
  };

  const handleToggleActive = async (entry: WhitelistEntry) => {
    try {
      await updateWhitelistEntry(entry.id, { is_active: !entry.is_active });
      loadWhitelist();
    } catch (err) {
      setError('Kon status niet wijzigen');
      console.error(err);
    }
  };

  const handleDelete = async (entryId: string) => {
    if (!confirm('Weet je zeker dat je dit nummer wilt verwijderen?')) return;
    
    try {
      await deleteWhitelistEntry(entryId);
      loadWhitelist();
    } catch (err) {
      setError('Kon nummer niet verwijderen');
      console.error(err);
    }
  };

  return (
    <Layout>
      <div className="px-4 sm:px-0">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Telefoonnummers Whitelist</h1>
            <p className="mt-2 text-gray-600">Beheer welke nummers toegang hebben tot de bot</p>
          </div>

          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Nummer Toevoegen
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Nieuw Nummer Toevoegen</DialogTitle>
                <DialogDescription>
                  Voeg een nieuw telefoonnummer toe aan de whitelist
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleAdd} className="space-y-4">
                <div>
                  <Label htmlFor="phone_number">Telefoonnummer *</Label>
                  <Input
                    id="phone_number"
                    placeholder="whatsapp:+31612345678"
                    value={formData.phone_number}
                    onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">Format: whatsapp:+31612345678</p>
                </div>
                <div>
                  <Label htmlFor="name">Naam *</Label>
                  <Input
                    id="name"
                    placeholder="Jan Jansen"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="department">Afdeling *</Label>
                  <Input
                    id="department"
                    placeholder="Manager"
                    value={formData.department}
                    onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="notes">Notities</Label>
                  <Input
                    id="notes"
                    placeholder="Extra informatie (optioneel)"
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
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
          <div className="text-center py-12">
            <p className="text-gray-500">Bezig met laden...</p>
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg overflow-hidden">
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
                {entries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-gray-500 py-8">
                      Geen nummers in de whitelist
                    </TableCell>
                  </TableRow>
                ) : (
                  entries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="font-medium">{entry.name}</TableCell>
                      <TableCell className="font-mono text-sm">{entry.phone_number}</TableCell>
                      <TableCell>{entry.department}</TableCell>
                      <TableCell className="text-sm text-gray-500">
                        {new Date(entry.added_at).toLocaleDateString('nl-NL')}
                      </TableCell>
                      <TableCell>
                        <Badge variant={entry.is_active ? 'default' : 'secondary'}>
                          {entry.is_active ? 'Actief' : 'Inactief'}
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
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </Layout>
  );
}