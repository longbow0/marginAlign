from nanopore.metaAnalyses.abstractMetaAnalysis import AbstractMetaAnalysis
import os, sys
import xml.etree.cElementTree as ET
from jobTree.src.bioio import system, fastqRead, fastaRead
from nanopore.analyses.utils import samIterator
from itertools import product
import numpy

class MarginAlignMetaAnalysis(AbstractMetaAnalysis):
    def run(self):
        readTypes = set([ readType for readFastqFile, readType in self.readFastqFiles ])
        coverageLevels = set()
        hash = {}
        variantCallingAlgorithms = set()
        proportionsHeldOut = set()
        for referenceFastaFile in self.referenceFastaFiles:
            for readType in readTypes:
                for readFastqFile, readFileReadType in self.readFastqFiles:
                    if readFileReadType == readType:
                        for mapper in self.mappers:
                            analyses, resultsDir = self.experimentHash[((readFastqFile, readType), referenceFastaFile, mapper)]
                            node = ET.parse(os.path.join(resultsDir, "analysis_MarginAlignSnpCaller", "marginaliseConsensus.xml")).getroot()
                            for c in node:
                                coverage = int(c.attrib["coverage"])
                                coverageLevels.add(coverage)
                                proportionHeldOut = float(c.attrib["totalHeldOut"]) / (float(c.attrib["totalHeldOut"]) + float(c.attrib["totalNonHeldOut"]))
                                key = (readType, mapper.__name__, c.tag, proportionHeldOut, referenceFastaFile)
                                variantCallingAlgorithms.add(c.tag)
                                proportionsHeldOut.add(proportionHeldOut)
                                if key not in hash:
                                    hash[key] = {}
                                if coverage not in hash[key]:
                                    hash[key][coverage] = []
                                hash[key][coverage].append(c)
                                
        fH = open(os.path.join(self.outputDir, "marginAlignAll.txt"), 'w')
        fH.write("\t".join(["readType", "mapper", "caller", 
                            "%heldOut", "coverage", 
                            "fScoreMin", "fScoreMedian", "fScoreMax",
                            "recallMin", "recallMedian", "recallMax",
                            "precisionMin", "precisionMedian", "precisionMax", 
                            "%notCalledMin", "%notCalledMedian", "%notCalledMax",
                            "actualCoverageMin", "actualCoverageMedian", "actualCoverageMax"]) + "\n")
        
        fH2 = open(os.path.join(self.outputDir, "marginAlignSquares.txt"), 'w')
        coverageLevels = list(coverageLevels)
        coverageLevels.sort()
        fH2.write("\t".join(["readType", "mapper", "caller", 
                            "%heldOut",
                           "\t".join([ ("recall_coverage_%s" % coverage) for coverage in coverageLevels]),
                           "\t".join([ ("precision_coverage_%s" % coverage) for coverage in coverageLevels]),
                           "\t".join([ ("fscore_coverage_%s" % coverage) for coverage in coverageLevels]) ]) + "\n")
        
        keys = hash.keys()
        keys.sort()
        
        rocCurvesHash = {}
        
        for readType, mapper, algorithm, proportionHeldOut, referenceFastaFile in keys:
            nodes = hash[(readType, mapper, algorithm, proportionHeldOut, referenceFastaFile)]
            
            recall = lambda c : float(c.attrib["totalHeldOutCallsTrue"])/float(c.attrib["totalHeldOut"]) if float(c.attrib["totalHeldOut"]) != 0 else 0
            precision = lambda c : float(c.attrib["totalHeldOutCallsTrue"])/(float(c.attrib["totalHeldOutCallsTrue"]) + float(c.attrib["totalFalsePositives"])) if float(c.attrib["totalHeldOutCallsTrue"]) + float(c.attrib["totalFalsePositives"]) != 0 else 0
            fScore = lambda c : 2 * precision(c) * recall(c) / (precision(c) + recall(c)) if precision(c) + recall(c) > 0 else 0
            notCalled = lambda c : (float(c.attrib["totalNonHeldOutNotCalled"])+float(c.attrib["totalHeldOutNotCalled"])) / (float(c.attrib["totalHeldOut"]) + float(c.attrib["totalNonHeldOut"]))
            actualCoverage = lambda c : float(c.attrib["actualCoverage"])
            
            for coverage in coverageLevels:
                def r(f):
                    i = map(f, nodes[coverage])
                    return "\t".join(map(str, (min(i), numpy.median(i), max(i))))
                fH.write("\t".join([readType, mapper, algorithm, str(proportionHeldOut), str(coverage), 
                                   r(fScore), r(recall), r(precision), r(notCalled), r(actualCoverage)]) + "\n")
            
            fH2.write("\t".join([readType, mapper, algorithm, str(proportionHeldOut)]) + "\t")
            fH2.write("\t".join(map(str, [ numpy.average(map(recall, nodes[coverage])) for coverage in coverageLevels ])) + "\t")
            fH2.write("\t".join(map(str, [ numpy.average(map(precision, nodes[coverage])) for coverage in coverageLevels ])) + "\t")
            fH2.write("\t".join(map(str, [ numpy.average(map(fScore, nodes[coverage])) for coverage in coverageLevels ])) + "\n")
            
            
            #Make ROC curves
            for coverage in coverageLevels:
                #Get the median true positive / median false positives
                falsePositiveRateByProbability = map(lambda c : map(float, c.attrib["falsePositiveRatesByProbability"].split()), nodes[coverage])
                truePositiveRateByProbability = map(lambda c : map(float, c.attrib["truePositiveRatesByProbability"].split()), nodes[coverage])
                precisionByProbability = map(lambda c : map(float, c.attrib["precisionByProbability"].split()), nodes[coverage])
                def merge(curves, fn):
                    return map(lambda i : fn(map(lambda curve : curve[i], curves)), range(len(curves[0])))
                avgFalsePositiveRatesByProbability = merge(falsePositiveRateByProbability, numpy.average)
                avgTruePositiveRatesByProbability = merge(falsePositiveRateByProbability, numpy.average)
                avgPrecisionByProbability = merge(precisionByProbability, numpy.average)
                rocCurvesHash[(readType, mapper, algorithm, proportionHeldOut, coverage)] = (avgFalsePositiveRatesByProbability, avgTruePositiveRatesByProbability, precisionByProbability)
        
        
        ####Ian todo ###
        
        #Place to create ROC / precision/recall plots
        variantCallingAlgorithms = list(variantCallingAlgorithms)
        variantCallingAlgorithms.sort()
        proportionsHeldOut = list(proportionsHeldOut)
        proportionsHeldOut.sort()
        for readType, mapper in product(readTypes, self.mappers):
            outf = open(os.path.join(self.getLocalTempDir(), "tmp.tsv"), "w")
            #Make grid plot for each combination of readType/mapper
            #Grid dimensions would be variant calling algorithms x proportion held out
            #On each plot we should show the roc curve (use falsePositiveRatesByProbability vs. truePositiveRatesByProbability) for the different coverages.
            for algorithm in variantCallingAlgorithms:
                for proportionHeldOut in proportionsHeldOut:
                    for coverage in coverageLevels:
                        falsePositiveRatesByProbability, truePositiveRatesByProbability, avgPrecisionByProbability = rocCurvesHash[(readType, mapper.__name__, algorithm, proportionHeldOut, coverage)]
                        outf.write("FPR\t{0}\t{1}\t{2}\t{3}\nTPR\t{0}\t{1}\t{2}\t{4}\n".format(str(algorithm), str(proportionHeldOut), str(coverage), "\t".join(map(str,falsePositiveRatesByProbability)), "\t".join(map(str,truePositiveRatesByProbability))))
            outf.close()
            system("Rscript nanopore/metaAnalyses/ROC_marginAlign.R {} {} {}".format(os.path.join(self.getLocalTempDir(), "tmp.tsv"), os.path.join(self.outputDir, readType + "_" + mapper.__name__ + "_ROC_curves.pdf"), len(variantCallingAlgorithms)))