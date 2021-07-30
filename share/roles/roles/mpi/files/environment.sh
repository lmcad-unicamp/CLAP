#!/bin/bash

prefix="-I"
parsed=$(mpicc --showme:compile)
stringarray=($parsed)
stringTemp=""
start=0
for i in "${stringarray[@]}"
do
   if [[ $start -gt 0 ]];
     then
       #Add prefix ':'
        stringTemp+=":"
   fi
   stringTemp+="${i/#$prefix}"
   start=$(($start+1))
done

#stringTemp+=$'\n'
exportString="export PATH=$stringTemp:$PATH"
            
echo "$(echo "$exportString"; cat .bashrc)" > .bashrc


prefix="-L"
parsed=$(mpicc --showme:link)
stringarray=($parsed)
stringTemp=""
start=0
for i in "${stringarray[@]}"
do
   if [[ $start -gt 0 ]];
     then
       #Add prefix ':' with the excpetion of the first
        stringTemp+=":"
   fi
   stringTemp+="${i/#$prefix}"
   start=$(($start+1))
done


#stringTemp+=$'\n'
exportString="export LD_LIBRARY_PATH=$stringTemp:$PATH"
echo "$(echo "$exportString"; cat .bashrc)" > .bashrc

