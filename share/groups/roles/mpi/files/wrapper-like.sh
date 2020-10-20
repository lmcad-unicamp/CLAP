#!/bin/bash

prefix="-I"
parsed=$(mpicc --showme:compile)
stringarray=($parsed)
stringTemp=""
for i in "${stringarray[@]}"
do
   stringTemp+="${i/#$prefix} "
done

#stringTemp+=$'\n'
exportString="export PATH=$stringTemp:$PATH"
            
echo "$(echo -n "$exportString"; cat .bashrc)" > .teste3



parsed=$(mpicc --showme:link)
stringarray=($parsed)
stringTemp=""
for i in "${stringarray[@]}"
do
   stringTemp+="${i/#$prefix} "
done

#stringTemp+=$'\n'
exportString="export LD_LIBRARY_PATH=$stringTemp:$PATH"
            
echo "$(echo -n "$exportString"; cat .teste3)" > .teste3

