import { useState, useEffect } from 'react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import NumberInput from '@/components/ui/NumberInput'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/Dialog'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import {
  getCollectionStats,
  startProductIngestion,
  ProductIngestionRequest,
  CollectionStatsResponse
} from '@/api/lightrag'
import { errorMessage } from '@/lib/utils'
import { toast } from 'sonner'
import { useBackendState } from '@/stores/state'
import { DatabaseIcon, PlayIcon, RefreshCwIcon, InfoIcon } from 'lucide-react'

interface ProductIngestionDialogProps {
  onIngestionStarted?: () => void
}

export default function ProductIngestionDialog({ onIngestionStarted }: ProductIngestionDialogProps) {
  const [open, setOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingStats, setIsLoadingStats] = useState(false)
  
  // Form state
  const [database, setDatabase] = useState('Zoftware')
  const [collection, setCollection] = useState('Products')
  const [batchSize, setBatchSize] = useState(25)
  const [workingDir, setWorkingDir] = useState('./rag_storage')
  
  // Stats state
  const [stats, setStats] = useState<CollectionStatsResponse | null>(null)
  const [statsError, setStatsError] = useState<string | null>(null)

  // Load collection stats when dialog opens or database/collection changes
  useEffect(() => {
    if (open && database && collection) {
      loadCollectionStats()
    }
  }, [open, database, collection])

  const loadCollectionStats = async () => {
    if (!database || !collection) return

    setIsLoadingStats(true)
    setStatsError(null)
    
    try {
      const collectionStats = await getCollectionStats(database, collection)
      setStats(collectionStats)
    } catch (err) {
      const error = errorMessage(err)
      setStatsError(error)
      toast.error(`Failed to load collection statistics: ${error}`)
    } finally {
      setIsLoadingStats(false)
    }
  }

  const handleStartIngestion = async () => {
    if (!database || !collection) {
      toast.error('Please fill in all required fields')
      return
    }

    setIsLoading(true)
    
    try {
      const request: ProductIngestionRequest = {
        database,
        collection,
        filter_query: { is_active: true }, // Only process active products
        limit: undefined, // Process all products - no limit
        skip: 0,
        batch_size: batchSize,
        working_dir: workingDir
      }

      const response = await startProductIngestion(request)
      
      toast.success(`Product ingestion job started successfully! Job ID: ${response.job_id}, Estimated batches: ${response.estimated_batches || 'unknown'}`)

      // Reset health check timer to pick up the new job
      useBackendState.getState().resetHealthCheckTimerDelayed(1000)

      // Close dialog and notify parent
      setOpen(false)
      onIngestionStarted?.()

    } catch (err) {
      const error = errorMessage(err)
      toast.error(`Failed to start product ingestion: ${error}`)
    } finally {
      setIsLoading(false)
    }
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat().format(num)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          tooltip="Ingest products from MongoDB database"
          side="bottom"
        >
          <DatabaseIcon className="h-4 w-4" />
          Ingest Products
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Product Ingestion</DialogTitle>
          <DialogDescription>
            Import product data from MongoDB into LightRAG for knowledge graph generation and semantic search.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6">
          {/* Database Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Database Configuration</CardTitle>
              <CardDescription>Configure the MongoDB connection details</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <label htmlFor="database" className="text-sm font-medium">
                    Database Name
                  </label>
                  <Input
                    id="database"
                    value={database}
                    onChange={(e) => setDatabase(e.target.value)}
                    placeholder="Zoftware"
                  />
                </div>
                <div className="grid gap-2">
                  <label htmlFor="collection" className="text-sm font-medium">
                    Collection Name
                  </label>
                  <Input
                    id="collection"
                    value={collection}
                    onChange={(e) => setCollection(e.target.value)}
                    placeholder="Products"
                  />
                </div>
              </div>
              
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadCollectionStats}
                  disabled={isLoadingStats || !database || !collection}
                >
                  <RefreshCwIcon className={`h-4 w-4 ${isLoadingStats ? 'animate-spin' : ''}`} />
                  Load Statistics
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Collection Statistics */}
          {stats && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <InfoIcon className="h-4 w-4" />
                  Collection Statistics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">
                      {formatNumber(stats.total_documents)}
                    </div>
                    <div className="text-sm text-gray-600">
                      Total Products
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">
                      {formatNumber(stats.estimated_batches)}
                    </div>
                    <div className="text-sm text-gray-600">
                      Estimated Batches
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">
                      {batchSize}
                    </div>
                    <div className="text-sm text-gray-600">
                      Batch Size
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-orange-600">
                      ~{Math.ceil(stats.estimated_batches * 2)}min
                    </div>
                    <div className="text-sm text-gray-600">
                      Est. Time
                    </div>
                  </div>
                </div>

                {stats.sample_product && (
                  <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                    <div className="text-sm font-medium mb-2">
                      Sample Product:
                    </div>
                    <div className="text-sm text-gray-700 dark:text-gray-300">
                      <strong>{stats.sample_product.product_name || 'Unknown Product'}</strong>
                      {stats.sample_product.company && (
                        <span className="ml-2">
                          by <em>{stats.sample_product.company}</em>
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Error Display */}
          {statsError && (
            <Card className="border-red-200 dark:border-red-800">
              <CardContent className="pt-4">
                <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
                  <InfoIcon className="h-4 w-4" />
                  <span className="text-sm">{statsError}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Processing Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Processing Configuration</CardTitle>
              <CardDescription>Configure how the products will be processed</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <label htmlFor="batchSize" className="text-sm font-medium">
                    Batch Size
                  </label>
                  <NumberInput
                    id="batchSize"
                    value={batchSize}
                    onValueChange={(value) => setBatchSize(value || 25)}
                    min={1}
                    max={100}
                    placeholder="25"
                  />
                  <div className="text-xs text-gray-500">
                    Number of products to process per batch (1-100)
                  </div>
                </div>
                <div className="grid gap-2">
                  <label htmlFor="workingDir" className="text-sm font-medium">
                    Working Directory
                  </label>
                  <Input
                    id="workingDir"
                    value={workingDir}
                    onChange={(e) => setWorkingDir(e.target.value)}
                    placeholder="./product_rag_storage"
                  />
                  <div className="text-xs text-gray-500">
                    Directory where LightRAG will store processed data
                  </div>
                </div>
              </div>

              {/* Processing Info */}
              <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="flex items-start gap-2">
                  <InfoIcon className="h-4 w-4 text-blue-600 mt-0.5" />
                  <div className="text-sm text-blue-800 dark:text-blue-200">
                    <div className="font-medium mb-1">
                      Processing Information
                    </div>
                    <ul className="text-xs space-y-1">
                      <li>• All active products will be processed (no limit)</li>
                      <li>• Progress can be monitored via Pipeline Status</li>
                      <li>• Large datasets will be processed in batches automatically</li>
                    </ul>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleStartIngestion}
            disabled={isLoading || !database || !collection || !stats}
          >
            {isLoading ? (
              <RefreshCwIcon className="h-4 w-4 animate-spin" />
            ) : (
              <PlayIcon className="h-4 w-4" />
            )}
            Start Ingestion
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
