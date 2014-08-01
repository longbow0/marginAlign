from jobTree.scriptTree.target import Target

class AbstractMetaAnalysis(Target):
    """Base class to for meta-analysis targets. Inherit this class to create a meta-analysis.
    """
    def __init__(self, outputDir, experiments):
        Target.__init__(self)
        self.experiments = experiments
        self.outputDir = outputDir
        
        #Triples of (readFastqFile, referenceFastaFile, mapper) to pairs of (analyses, resultsDir)
        self.experimentHash = {}
        #Mappers
        self.mappers = set()
        #Read files
        self.readFastqFiles = set()
        #Reference files
        self.referenceFastaFiles = set()
        
        #Store all this stuff
        for readFastqFile, referenceFastaFile, mapper, analyses, resultsDir in self.experiments:
            self.experimentHash[(readFastqFile, referenceFastaFile, mapper)] = (analyses, resultsDir)
            self.mappers.add(mapper)
            self.readFastqFiles.add(readFastqFile)
            self.referenceFastaFiles.add(referenceFastaFile)